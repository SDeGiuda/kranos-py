"""
Módulo de captura de imágenes.

Intenta usar picamera2 (disponible sólo en Raspberry Pi).  Si no está
instalada, hace fallback a OpenCV (cv2).  Si tampoco está disponible,
lanza un ImportError con un mensaje descriptivo.
"""

import datetime
import logging
import os
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)


def _try_import_picamera2():
    try:
        from picamera2 import Picamera2  # noqa: F401
        return True
    except ImportError:
        return False


def _try_import_cv2():
    try:
        import cv2  # noqa: F401
        return True
    except ImportError:
        return False


class Camera:
    """Abstracción de la cámara que soporta picamera2 y OpenCV."""

    def __init__(self, image_dir: str, resolution: Tuple[int, int] = (1280, 720)):
        """
        Args:
            image_dir: Directorio donde se guardarán las imágenes capturadas.
            resolution: Tupla (ancho, alto) de la resolución deseada.
        """
        self.image_dir = Path(image_dir)
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.resolution = resolution
        self._camera = None
        self._backend: str = ""

        if _try_import_picamera2():
            self._backend = "picamera2"
            logger.info("Backend de cámara: picamera2")
        elif _try_import_cv2():
            self._backend = "opencv"
            logger.info("Backend de cámara: OpenCV")
        else:
            raise ImportError(
                "No se encontró ningún backend de cámara compatible. "
                "Instale 'picamera2' (Raspberry Pi) o 'opencv-python'."
            )

    # ------------------------------------------------------------------
    def open(self) -> None:
        """Inicializa y abre la cámara."""
        if self._backend == "picamera2":
            from picamera2 import Picamera2

            self._camera = Picamera2()
            config = self._camera.create_still_configuration(
                main={"size": self.resolution}
            )
            self._camera.configure(config)
            self._camera.start()
            logger.info("Cámara picamera2 iniciada.")
        elif self._backend == "opencv":
            import cv2

            self._camera = cv2.VideoCapture(0)
            self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            if not self._camera.isOpened():
                raise RuntimeError("No se pudo abrir la cámara con OpenCV.")
            logger.info("Cámara OpenCV iniciada.")

    def close(self) -> None:
        """Libera los recursos de la cámara."""
        if self._camera is None:
            return
        try:
            if self._backend == "picamera2":
                self._camera.stop()
                self._camera.close()
            elif self._backend == "opencv":
                self._camera.release()
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Error al cerrar la cámara: %s", exc)
        finally:
            self._camera = None

    def capture(self) -> str:
        """
        Captura una imagen y la guarda en ``image_dir``.

        Returns:
            Ruta absoluta al archivo de imagen guardado.
        """
        if self._camera is None:
            self.open()

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.image_dir / f"capture_{timestamp}.jpg"

        if self._backend == "picamera2":
            self._camera.capture_file(str(filename))
        elif self._backend == "opencv":
            import cv2

            ret, frame = self._camera.read()
            if not ret:
                raise RuntimeError("No se pudo capturar el frame de la cámara.")
            cv2.imwrite(str(filename), frame)

        logger.info("Imagen capturada: %s", filename)
        return str(filename)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.close()


def cleanup_old_images(image_dir: str, max_images: int) -> None:
    """Elimina las imágenes más antiguas si se supera ``max_images``."""
    image_dir_path = Path(image_dir)
    images = sorted(
        image_dir_path.glob("capture_*.jpg"),
        key=os.path.getmtime,
    )
    excess = len(images) - max_images
    if excess > 0:
        for img in images[:excess]:
            try:
                img.unlink()
                logger.debug("Imagen eliminada por límite: %s", img)
            except OSError as exc:
                logger.warning("No se pudo eliminar %s: %s", img, exc)
