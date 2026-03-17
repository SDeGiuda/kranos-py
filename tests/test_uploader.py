"""Pruebas unitarias para src/uploader.py."""

import pytest
from unittest.mock import MagicMock, patch

from src.uploader import EventUploader, is_connected


# ── is_connected ──────────────────────────────────────────────────────────────

def test_is_connected_returns_true_on_success():
    with patch("src.uploader.socket.socket") as mock_socket_cls:
        mock_sock = MagicMock()
        mock_socket_cls.return_value.__enter__ = lambda s: mock_sock
        mock_socket_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_sock.connect.return_value = None
        assert is_connected() is True


def test_is_connected_returns_false_on_oserror():
    with patch("src.uploader.socket.socket") as mock_socket_cls:
        mock_sock = MagicMock()
        mock_socket_cls.return_value.__enter__ = lambda s: mock_sock
        mock_socket_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_sock.connect.side_effect = OSError("unreachable")
        assert is_connected() is False


# ── EventUploader ─────────────────────────────────────────────────────────────

@pytest.fixture
def uploader():
    return EventUploader(
        backend_url="http://test-backend",
        events_endpoint="/api/events",
        timeout_seconds=5,
        batch_size=10,
    )


def test_uploader_url(uploader):
    assert uploader.url == "http://test-backend/api/events"


def test_upload_event_success(uploader):
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.raise_for_status.return_value = None

    with patch("src.uploader.requests.post", return_value=mock_response) as mock_post:
        result = uploader.upload_event({"id": 1, "device_id": "rpi-001"})

    assert result is True
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert call_kwargs[1]["json"] == {"id": 1, "device_id": "rpi-001"}


def test_upload_event_server_error_returns_false(uploader):
    import requests as req_lib

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = req_lib.exceptions.HTTPError("500")

    with patch("src.uploader.requests.post", return_value=mock_response):
        result = uploader.upload_event({"id": 2})

    assert result is False


def test_upload_event_connection_error_returns_false(uploader):
    import requests as req_lib

    with patch(
        "src.uploader.requests.post",
        side_effect=req_lib.exceptions.ConnectionError("no route"),
    ):
        result = uploader.upload_event({"id": 3})

    assert result is False


# ── sync_pending ──────────────────────────────────────────────────────────────

def test_sync_pending_marks_successful_events(uploader):
    """sync_pending debe marcar como sincronizados los eventos del lote enviado."""
    mock_storage = MagicMock()
    mock_storage.get_pending_events.return_value = [
        {"id": 10, "device_id": "rpi-001"},
        {"id": 11, "device_id": "rpi-001"},
    ]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None

    with patch("src.uploader.requests.post", return_value=mock_response):
        synced = uploader.sync_pending(mock_storage)

    assert synced == 2
    mock_storage.mark_as_synced.assert_called_once_with([10, 11])


def test_sync_pending_no_events_returns_zero(uploader):
    mock_storage = MagicMock()
    mock_storage.get_pending_events.return_value = []

    synced = uploader.sync_pending(mock_storage)

    assert synced == 0
    mock_storage.mark_as_synced.assert_not_called()


def test_sync_pending_batch_failure_marks_no_events(uploader):
    """Si el lote falla, ningún evento debe marcarse como sincronizado."""
    import requests as req_lib

    mock_storage = MagicMock()
    mock_storage.get_pending_events.return_value = [
        {"id": 20},
        {"id": 21},
    ]

    err_response = MagicMock()
    err_response.raise_for_status.side_effect = req_lib.exceptions.HTTPError("500")

    with patch("src.uploader.requests.post", return_value=err_response):
        synced = uploader.sync_pending(mock_storage)

    assert synced == 0
    mock_storage.mark_as_synced.assert_not_called()
