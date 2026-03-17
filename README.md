# kranos-py

Módulo Python que corre en una Raspberry Pi para la detección y reconocimiento de empleados sin casco en obra.

## Descripción

El sistema realiza capturas de imagen de manera periódica, detecta localmente la cantidad de personas presentes y si utilizan casco, registra la temperatura ambiente, persiste los eventos en una base de datos local y los sincroniza con el backend cloud cuando hay conectividad.

### Arquitectura

```
kranos-py/
├── main.py                 # Punto de entrada – bucle de orquestación
├── config.yaml             # Configuración del sistema
├── requirements.txt        # Dependencias Python
├── src/
│   ├── capture.py          # Captura de imágenes (picamera2 / OpenCV)
│   ├── config.py           # Carga de configuración
│   ├── detector.py         # Detección de cascos (YOLOv8)
│   ├── storage.py          # Persistencia local SQLite
│   ├── temperature.py      # Lectura de sensor de temperatura (DHT11/DHT22)
│   └── uploader.py         # Carga de eventos al backend cloud
├── tests/
│   ├── test_detector.py
│   ├── test_storage.py
│   └── test_uploader.py
├── models/                 # Pesos del modelo YOLOv8 (no incluidos en el repo)
└── data/
    └── images/             # Imágenes capturadas (generadas en tiempo de ejecución)
```

## Requisitos

- Python 3.9+
- Raspberry Pi 4 (recomendado) con:
  - Módulo de cámara (picamera2)
  - Sensor de temperatura DHT11 o DHT22 conectado a un pin GPIO

## Instalación

```bash
pip install -r requirements.txt
# Sólo en Raspberry Pi:
pip install picamera2 adafruit-circuitpython-dht
```

## Configuración

Editar `config.yaml` antes de ejecutar:

| Sección     | Parámetro              | Descripción                                      |
|-------------|------------------------|--------------------------------------------------|
| `capture`   | `interval_seconds`     | Segundos entre capturas (por defecto: 30)        |
| `capture`   | `resolution`           | Resolución de la cámara `[ancho, alto]`          |
| `capture`   | `max_images`           | Máximo de imágenes a retener localmente          |
| `detector`  | `model_path`           | Ruta al modelo YOLOv8 entrenado                  |
| `detector`  | `confidence_threshold` | Confianza mínima para aceptar una detección      |
| `temperature`| `sensor_type`         | `DHT11`, `DHT22` o `MOCK`                        |
| `temperature`| `gpio_pin`            | Pin GPIO BCM del sensor                          |
| `storage`   | `db_path`              | Ruta al archivo SQLite de eventos                |
| `uploader`  | `backend_url`          | URL base del backend cloud                       |
| `device`    | `id`                   | Identificador único del dispositivo              |

## Ejecución

```bash
python main.py
# O especificando un config alternativo:
python main.py --config /ruta/a/config.yaml
```

El sistema puede detenerse limpiamente con `Ctrl+C` o enviando `SIGTERM`.

## Modelo de detección

Se espera un modelo YOLOv8 entrenado con dos clases:
- Clase `0`: persona **con** casco
- Clase `1`: persona **sin** casco

Los IDs de clase son configurables en `config.yaml` (`detector.helmet_class_id` y `detector.no_helmet_class_id`).

Si el modelo no se encuentra en la ruta configurada, el sistema arranca en modo **MOCK** (detector simulado), útil para desarrollo y pruebas sin hardware.

## Estructura del evento

Cada evento generado tiene la siguiente estructura:

```json
{
  "device_id": "rpi-001",
  "captured_at": "2024-01-01T10:00:00Z",
  "total_persons": 3,
  "persons_with_helmet": 2,
  "persons_without_helmet": 1,
  "temperature": 24.5,
  "no_helmet_detections": [
    { "x1": 100, "y1": 150, "x2": 200, "y2": 300, "confidence": 0.95 }
  ],
  "image_path": "/home/pi/kranos-py/data/images/capture_20240101_100000.jpg"
}
```

## Pruebas

```bash
pytest tests/ -v
```

## Operación sin conectividad

Cuando no hay conexión a internet, los eventos se almacenan localmente en SQLite y se sincronizan automáticamente con el backend en la siguiente captura en que haya conectividad disponible.
