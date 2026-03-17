"""
Kranos-Py – Módulo principal.

Punto de entrada del sistema de monitoreo de cascos en obra.
Orquesta el ciclo periódico de:
  1. Captura de imagen.
  2. Detección local de personas con/sin casco.
  3. Lectura de temperatura.
  4. Persistencia local del evento.
  5. Intento de sincronización con el backend cloud.

Uso:
  python main.py [--config path/to/config.yaml]
"""

import argparse
import datetime
import logging
import os
import signal
import sys
import time

# Asegura que src/ esté en el path cuando se ejecuta desde el raíz
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.capture import Camera, cleanup_old_images
from src.config import load_config, resolve_path
from src.detector import HelmDetector, MockHelmDetector
from src.storage import LocalStorage
from src.temperature import TemperatureSensor
from src.uploader import EventUploader, is_connected

# ── Configuración de logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("kranos")

# ── Control de parada limpia ──────────────────────────────────────────────────
_running = True


def _handle_signal(signum, _frame):
    global _running
    logger.info("Señal %d recibida. Deteniendo el sistema…", signum)
    _running = False


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ──────────────────────────────────────────────────────────────────────────────


def build_components(cfg: dict):
    """Construye e inicializa los componentes a partir de la configuración."""
    capture_cfg = cfg.get("capture", {})
    detector_cfg = cfg.get("detector", {})
    temp_cfg = cfg.get("temperature", {})
    storage_cfg = cfg.get("storage", {})
    uploader_cfg = cfg.get("uploader", {})

    image_dir = resolve_path(capture_cfg.get("image_dir", "data/images"))
    resolution = tuple(capture_cfg.get("resolution", [1280, 720]))

    camera = Camera(image_dir=image_dir, resolution=resolution)

    model_path = resolve_path(detector_cfg.get("model_path", "models/helmet_detector.pt"))
    use_mock_detector = not os.path.exists(model_path)
    if use_mock_detector:
        logger.warning(
            "Modelo no encontrado en '%s'. Se usará el detector MOCK.", model_path
        )
        detector = MockHelmDetector()
    else:
        detector = HelmDetector(
            model_path=model_path,
            confidence_threshold=detector_cfg.get("confidence_threshold", 0.5),
            helmet_class_id=detector_cfg.get("helmet_class_id", 0),
            no_helmet_class_id=detector_cfg.get("no_helmet_class_id", 1),
            imgsz=detector_cfg.get("imgsz", 640),
        )

    temp_sensor = TemperatureSensor(
        sensor_type=temp_cfg.get("sensor_type", "MOCK"),
        gpio_pin=temp_cfg.get("gpio_pin", 4),
        default_celsius=temp_cfg.get("default_celsius", 25.0),
    )

    db_path = resolve_path(storage_cfg.get("db_path", "data/events.db"))
    storage = LocalStorage(db_path=db_path)

    uploader = EventUploader(
        backend_url=uploader_cfg.get("backend_url", "http://localhost:8000"),
        events_endpoint=uploader_cfg.get("events_endpoint", "/api/events"),
        timeout_seconds=uploader_cfg.get("timeout_seconds", 10),
        batch_size=uploader_cfg.get("batch_size", 20),
    )

    return camera, detector, temp_sensor, storage, uploader


def run_cycle(
    camera: Camera,
    detector,
    temp_sensor: TemperatureSensor,
    storage: LocalStorage,
    uploader: EventUploader,
    cfg: dict,
) -> None:
    """Ejecuta un ciclo completo de captura-detección-almacenamiento-sincronización."""
    device_id = cfg.get("device", {}).get("id", "rpi-001")
    capture_cfg = cfg.get("capture", {})

    # 1. Captura
    image_path = camera.capture()

    # 2. Detección
    detection_result = detector.detect(image_path)

    # 3. Temperatura
    temperature = temp_sensor.read()

    # 4. Construcción del evento
    captured_at = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    event = {
        "device_id": device_id,
        "captured_at": captured_at,
        "total_persons": detection_result.total_persons,
        "persons_with_helmet": detection_result.persons_with_helmet,
        "persons_without_helmet": detection_result.persons_without_helmet,
        "temperature": temperature,
        "no_helmet_detections": detection_result.to_dict()["no_helmet_detections"],
        "image_path": image_path,
    }

    # 5. Persistencia local
    event_id = storage.save_event(event)
    event["id"] = event_id

    # 6. Sincronización si hay conectividad
    if is_connected():
        uploader.sync_pending(storage)
    else:
        logger.info("Sin conectividad. El evento ID=%d queda en cola local.", event_id)

    # 7. Limpieza de imágenes antiguas
    max_images = capture_cfg.get("max_images", 200)
    cleanup_old_images(str(camera.image_dir), max_images)


def main(config_path: str) -> None:
    """Función principal del sistema."""
    cfg = load_config(config_path)
    interval = cfg.get("capture", {}).get("interval_seconds", 30)

    logger.info("Iniciando Kranos-Py (intervalo: %d s)…", interval)

    camera, detector, temp_sensor, storage, uploader = build_components(cfg)

    try:
        camera.open()
        while _running:
            cycle_start = time.monotonic()
            try:
                run_cycle(camera, detector, temp_sensor, storage, uploader, cfg)
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Error en el ciclo de captura: %s", exc, exc_info=True)

            elapsed = time.monotonic() - cycle_start
            sleep_time = max(0, interval - elapsed)
            logger.debug("Próxima captura en %.1f s.", sleep_time)

            # Espera interrumpible para responder rápido a señales de parada
            end = time.monotonic() + sleep_time
            while _running and time.monotonic() < end:
                time.sleep(min(1.0, end - time.monotonic()))
    finally:
        camera.close()
        temp_sensor.close()
        logger.info("Kranos-Py detenido.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Kranos-Py – Monitor de cascos en obra (Raspberry Pi)"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Ruta al archivo de configuración YAML (por defecto: config.yaml)",
    )
    args = parser.parse_args()
    main(args.config)
