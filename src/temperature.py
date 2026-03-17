"""
Módulo de lectura de temperatura.

Soporta los sensores DHT11 y DHT22 conectados a un pin GPIO de la
Raspberry Pi mediante la librería adafruit-circuitpython-dht.

Si el sensor no está disponible (modo MOCK o ausencia de hardware), retorna
un valor por defecto configurable.
"""

import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class SensorType(str, Enum):
    DHT11 = "DHT11"
    DHT22 = "DHT22"
    MOCK = "MOCK"


class TemperatureSensor:
    """Lee la temperatura ambiente desde un sensor DHT11/DHT22."""

    def __init__(
        self,
        sensor_type: str = "DHT22",
        gpio_pin: int = 4,
        default_celsius: float = 25.0,
    ):
        """
        Args:
            sensor_type: Tipo de sensor: "DHT11", "DHT22" o "MOCK".
            gpio_pin: Número de pin GPIO (numeración BCM) al que está conectado
                el sensor.
            default_celsius: Temperatura por defecto cuando el sensor no está
                disponible o falla la lectura.
        """
        self.sensor_type = SensorType(sensor_type.upper())
        self.gpio_pin = gpio_pin
        self.default_celsius = default_celsius
        self._sensor = None

    def _init_sensor(self):
        """Inicializa el objeto sensor de Adafruit de forma diferida."""
        if self._sensor is not None or self.sensor_type == SensorType.MOCK:
            return
        try:
            import adafruit_dht  # pylint: disable=import-outside-toplevel
            import board  # pylint: disable=import-outside-toplevel

            pin = getattr(board, f"D{self.gpio_pin}", None)
            if pin is None:
                raise ValueError(
                    f"Pin GPIO D{self.gpio_pin} no encontrado en el módulo 'board'."
                )

            if self.sensor_type == SensorType.DHT11:
                self._sensor = adafruit_dht.DHT11(pin)
            else:
                self._sensor = adafruit_dht.DHT22(pin)

            logger.info(
                "Sensor %s inicializado en GPIO %d.", self.sensor_type.value, self.gpio_pin
            )
        except (ImportError, ValueError) as exc:
            logger.warning(
                "No se pudo inicializar el sensor de temperatura (%s). "
                "Se usará el valor por defecto %.1f°C. Detalle: %s",
                self.sensor_type.value,
                self.default_celsius,
                exc,
            )
            self.sensor_type = SensorType.MOCK

    def read(self) -> float:
        """
        Lee la temperatura actual en grados Celsius.

        Si el sensor falla o no está disponible, retorna ``default_celsius``.

        Returns:
            Temperatura en °C.
        """
        self._init_sensor()

        if self.sensor_type == SensorType.MOCK:
            logger.debug("Sensor MOCK: retornando %.1f°C", self.default_celsius)
            return self.default_celsius

        temperature: Optional[float] = None
        try:
            temperature = self._sensor.temperature
            if temperature is None:
                raise RuntimeError("El sensor retornó None.")
            logger.debug("Temperatura leída: %.1f°C", temperature)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "Error al leer temperatura (%s). Se usa valor por defecto %.1f°C. "
                "Detalle: %s",
                self.sensor_type.value,
                self.default_celsius,
                exc,
            )
            temperature = self.default_celsius

        return float(temperature)

    def close(self) -> None:
        """Libera los recursos del sensor."""
        if self._sensor is not None:
            try:
                self._sensor.exit()
            except Exception:  # pylint: disable=broad-except
                pass
            finally:
                self._sensor = None
