"""
Módulo de carga de eventos al backend cloud.

Verifica la conectividad antes de intentar enviar datos.  Trabaja junto
con LocalStorage: obtiene los eventos pendientes, los envía y, si tienen
éxito, los marca como sincronizados.

Los eventos se envían en lotes (batch) para minimizar el número de
peticiones HTTP.
"""

import logging
import socket
from typing import List

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Dominio que se usa para verificar conectividad (no se accede a él, sólo
# se comprueba que la resolución DNS y el socket TCP funcionen).
_CONNECTIVITY_HOST = "8.8.8.8"
_CONNECTIVITY_PORT = 53
_CONNECTIVITY_TIMEOUT = 3


def is_connected(
    host: str = _CONNECTIVITY_HOST,
    port: int = _CONNECTIVITY_PORT,
    timeout: float = _CONNECTIVITY_TIMEOUT,
) -> bool:
    """
    Comprueba si hay conectividad de red intentando abrir un socket TCP.

    Args:
        host: Dirección IP o nombre de host a comprobar.
        port: Puerto TCP destino.
        timeout: Segundos de espera.

    Returns:
        ``True`` si hay conectividad, ``False`` en caso contrario.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((host, port))
        return True
    except OSError:
        return False


class EventUploader:
    """Envía eventos al backend cloud mediante HTTP POST."""

    def __init__(
        self,
        backend_url: str,
        events_endpoint: str = "/api/events",
        timeout_seconds: int = 10,
        batch_size: int = 20,
    ):
        """
        Args:
            backend_url: URL base del backend (ej. ``http://api.example.com``).
            events_endpoint: Ruta del endpoint de eventos.
            timeout_seconds: Timeout para cada petición HTTP.
            batch_size: Cantidad máxima de eventos por lote.
        """
        if requests is None:
            raise ImportError(
                "El paquete 'requests' no está instalado. "
                "Ejecute: pip install requests"
            )
        self.backend_url = backend_url.rstrip("/")
        self.events_endpoint = events_endpoint
        self.timeout = timeout_seconds
        self.batch_size = batch_size

    @property
    def url(self) -> str:
        """URL completa del endpoint de eventos."""
        return self.backend_url + self.events_endpoint

    def upload_event(self, event: dict) -> bool:
        """
        Envía un único evento al backend.

        Args:
            event: Diccionario con los datos del evento.

        Returns:
            ``True`` si el servidor respondió con un código 2xx.
        """
        try:
            response = requests.post(
                self.url,
                json=event,
                timeout=self.timeout,
            )
            response.raise_for_status()
            logger.info(
                "Evento enviado exitosamente (ID local=%s, status=%d).",
                event.get("id"),
                response.status_code,
            )
            return True
        except requests.exceptions.RequestException as exc:
            logger.warning("Error al enviar evento (ID local=%s): %s", event.get("id"), exc)
            return False

    def upload_batch(self, events: List[dict]) -> List[int]:
        """
        Envía una lista de eventos en un único POST en lote.

        Args:
            events: Lista de dicts de eventos.

        Returns:
            Lista de IDs locales de los eventos enviados exitosamente.
        """
        if not events:
            return []

        successful_ids: List[int] = []

        try:
            response = requests.post(
                self.url + "/batch",
                json=events,
                timeout=self.timeout,
            )
            response.raise_for_status()
            successful_ids = [e["id"] for e in events if "id" in e]
            logger.info(
                "Lote de %d eventos enviado exitosamente (status=%d).",
                len(events),
                response.status_code,
            )
        except requests.exceptions.RequestException as exc:
            logger.warning("Error al enviar lote de eventos: %s", exc)

        return successful_ids

    def sync_pending(self, storage) -> int:
        """
        Obtiene los eventos pendientes de ``storage``, los envía al backend
        y los marca como sincronizados.

        Args:
            storage: Instancia de ``LocalStorage``.

        Returns:
            Cantidad de eventos sincronizados exitosamente.
        """
        pending = storage.get_pending_events(limit=self.batch_size)
        if not pending:
            logger.debug("No hay eventos pendientes de sincronización.")
            return 0

        logger.info("Sincronizando %d eventos pendientes…", len(pending))

        synced_ids: List[int] = self.upload_batch(pending)

        if synced_ids:
            storage.mark_as_synced(synced_ids)

        logger.info(
            "Sincronización completada: %d/%d eventos enviados.",
            len(synced_ids),
            len(pending),
        )
        return len(synced_ids)
