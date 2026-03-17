"""
Módulo de almacenamiento local.

Persiste los eventos generados por el sistema en una base de datos SQLite
local.  Los eventos se marcan como "pendientes" hasta que son enviados
exitosamente al backend cloud.

Esquema de la tabla ``events``:
  id                  INTEGER PRIMARY KEY
  device_id           TEXT
  captured_at         TEXT  (ISO-8601 UTC)
  total_persons       INTEGER
  persons_with_helmet INTEGER
  persons_without_helmet INTEGER
  temperature         REAL
  no_helmet_detections TEXT  (JSON)
  image_path          TEXT
  synced              INTEGER (0 = pendiente, 1 = enviado)
  created_at          TEXT  (ISO-8601 UTC, registro interno)
"""

import datetime
import json
import logging
import sqlite3
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Columnas devueltas al consultar eventos
EVENT_COLUMNS = (
    "id",
    "device_id",
    "captured_at",
    "total_persons",
    "persons_with_helmet",
    "persons_without_helmet",
    "temperature",
    "no_helmet_detections",
    "image_path",
    "synced",
    "created_at",
)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id              TEXT    NOT NULL,
    captured_at            TEXT    NOT NULL,
    total_persons          INTEGER NOT NULL DEFAULT 0,
    persons_with_helmet    INTEGER NOT NULL DEFAULT 0,
    persons_without_helmet INTEGER NOT NULL DEFAULT 0,
    temperature            REAL,
    no_helmet_detections   TEXT    NOT NULL DEFAULT '[]',
    image_path             TEXT,
    synced                 INTEGER NOT NULL DEFAULT 0,
    created_at             TEXT    NOT NULL
);
"""


class LocalStorage:
    """Interfaz SQLite para persistencia local de eventos."""

    def __init__(self, db_path: str):
        """
        Args:
            db_path: Ruta al archivo SQLite (se crea si no existe).
        """
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Inicialización
    # ------------------------------------------------------------------
    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(CREATE_TABLE_SQL)
        logger.info("Base de datos local inicializada: %s", self.db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------
    def save_event(self, event: dict) -> int:
        """
        Guarda un evento en la base de datos local.

        Args:
            event: Diccionario con las claves del evento (ver esquema).

        Returns:
            ID del evento recién insertado.
        """
        now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        no_helmet_json = json.dumps(
            event.get("no_helmet_detections", []), ensure_ascii=False
        )

        sql = """
        INSERT INTO events
            (device_id, captured_at, total_persons, persons_with_helmet,
             persons_without_helmet, temperature, no_helmet_detections,
             image_path, synced, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """
        params = (
            event.get("device_id", ""),
            event.get("captured_at", now),
            event.get("total_persons", 0),
            event.get("persons_with_helmet", 0),
            event.get("persons_without_helmet", 0),
            event.get("temperature"),
            no_helmet_json,
            event.get("image_path"),
            now,
        )

        with self._connect() as conn:
            cursor = conn.execute(sql, params)
            event_id: int = cursor.lastrowid

        logger.debug("Evento guardado localmente con ID=%d", event_id)
        return event_id

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    def get_pending_events(self, limit: Optional[int] = None) -> List[dict]:
        """
        Retorna los eventos aún no sincronizados con el backend.

        Args:
            limit: Límite máximo de resultados (``None`` = sin límite).

        Returns:
            Lista de dicts con los datos de cada evento.
        """
        sql = "SELECT * FROM events WHERE synced = 0 ORDER BY captured_at ASC"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"

        with self._connect() as conn:
            rows = conn.execute(sql).fetchall()

        return [self._row_to_dict(r) for r in rows]

    def get_all_events(self) -> List[dict]:
        """Retorna todos los eventos ordenados por fecha de captura."""
        sql = "SELECT * FROM events ORDER BY captured_at DESC"
        with self._connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Actualización
    # ------------------------------------------------------------------
    def mark_as_synced(self, event_ids: List[int]) -> None:
        """
        Marca los eventos indicados como sincronizados.

        Args:
            event_ids: Lista de IDs de eventos a marcar.
        """
        if not event_ids:
            return
        placeholders = ",".join("?" * len(event_ids))
        sql = f"UPDATE events SET synced = 1 WHERE id IN ({placeholders})"
        with self._connect() as conn:
            conn.execute(sql, event_ids)
        logger.debug("Eventos marcados como sincronizados: %s", event_ids)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        try:
            d["no_helmet_detections"] = json.loads(d.get("no_helmet_detections", "[]"))
        except (json.JSONDecodeError, TypeError):
            d["no_helmet_detections"] = []
        return d
