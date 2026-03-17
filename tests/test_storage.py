"""Pruebas unitarias para src/storage.py."""

import json
import os
import tempfile

import pytest

from src.storage import LocalStorage


@pytest.fixture
def db(tmp_path):
    """Base de datos temporal para cada prueba."""
    return LocalStorage(db_path=str(tmp_path / "test_events.db"))


# ── save_event ────────────────────────────────────────────────────────────────

def test_save_event_returns_integer_id(db):
    event_id = db.save_event({
        "device_id": "rpi-001",
        "captured_at": "2024-01-01T10:00:00Z",
        "total_persons": 3,
        "persons_with_helmet": 2,
        "persons_without_helmet": 1,
        "temperature": 22.5,
        "no_helmet_detections": [{"x1": 10, "y1": 20, "x2": 50, "y2": 80, "confidence": 0.9}],
        "image_path": "/tmp/img.jpg",
    })
    assert isinstance(event_id, int)
    assert event_id >= 1


def test_save_multiple_events_increments_ids(db):
    id1 = db.save_event({"device_id": "rpi-001", "captured_at": "2024-01-01T10:00:00Z"})
    id2 = db.save_event({"device_id": "rpi-001", "captured_at": "2024-01-01T10:00:30Z"})
    assert id2 > id1


def test_save_event_with_minimal_fields(db):
    event_id = db.save_event({})
    assert event_id >= 1


# ── get_pending_events ────────────────────────────────────────────────────────

def test_new_events_are_pending(db):
    db.save_event({"device_id": "rpi-001", "captured_at": "2024-01-01T10:00:00Z"})
    pending = db.get_pending_events()
    assert len(pending) == 1


def test_pending_events_limit(db):
    for i in range(5):
        db.save_event({"captured_at": f"2024-01-01T10:00:0{i}Z"})
    pending = db.get_pending_events(limit=3)
    assert len(pending) == 3


def test_no_pending_after_sync(db):
    event_id = db.save_event({"device_id": "rpi-001", "captured_at": "2024-01-01T10:00:00Z"})
    db.mark_as_synced([event_id])
    pending = db.get_pending_events()
    assert pending == []


# ── mark_as_synced ────────────────────────────────────────────────────────────

def test_mark_as_synced_removes_from_pending(db):
    id1 = db.save_event({"captured_at": "2024-01-01T10:00:00Z"})
    id2 = db.save_event({"captured_at": "2024-01-01T10:00:30Z"})
    db.mark_as_synced([id1])
    pending = db.get_pending_events()
    assert len(pending) == 1
    assert pending[0]["id"] == id2


def test_mark_as_synced_empty_list_is_noop(db):
    db.save_event({"captured_at": "2024-01-01T10:00:00Z"})
    db.mark_as_synced([])
    assert len(db.get_pending_events()) == 1


# ── no_helmet_detections JSON serialization ───────────────────────────────────

def test_no_helmet_detections_serialized_and_deserialized(db):
    detections = [{"x1": 10, "y1": 20, "x2": 50, "y2": 80, "confidence": 0.95}]
    db.save_event({"captured_at": "2024-01-01T10:00:00Z", "no_helmet_detections": detections})
    events = db.get_all_events()
    assert events[0]["no_helmet_detections"] == detections


def test_missing_no_helmet_detections_defaults_to_empty_list(db):
    db.save_event({"captured_at": "2024-01-01T10:00:00Z"})
    events = db.get_all_events()
    assert events[0]["no_helmet_detections"] == []


# ── get_all_events ────────────────────────────────────────────────────────────

def test_get_all_events_includes_synced_and_pending(db):
    id1 = db.save_event({"captured_at": "2024-01-01T10:00:00Z"})
    db.save_event({"captured_at": "2024-01-01T10:00:30Z"})
    db.mark_as_synced([id1])
    all_events = db.get_all_events()
    assert len(all_events) == 2
