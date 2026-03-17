"""Pruebas unitarias para src/detector.py."""

import pytest

from src.detector import (
    Detection,
    DetectionResult,
    HelmDetector,
    MockHelmDetector,
)


# ── DetectionResult.to_dict ───────────────────────────────────────────────────

def test_detection_result_to_dict_structure():
    result = DetectionResult(
        total_persons=3,
        persons_with_helmet=2,
        persons_without_helmet=1,
        no_helmet_detections=[
            Detection(x1=10, y1=20, x2=50, y2=80, confidence=0.92)
        ],
    )
    d = result.to_dict()
    assert d["total_persons"] == 3
    assert d["persons_with_helmet"] == 2
    assert d["persons_without_helmet"] == 1
    assert len(d["no_helmet_detections"]) == 1
    det = d["no_helmet_detections"][0]
    assert det["x1"] == 10
    assert det["y1"] == 20
    assert det["x2"] == 50
    assert det["y2"] == 80
    assert det["confidence"] == pytest.approx(0.92, abs=1e-4)


def test_detection_result_to_dict_rounds_confidence():
    result = DetectionResult(
        total_persons=1,
        persons_with_helmet=0,
        persons_without_helmet=1,
        no_helmet_detections=[
            Detection(x1=0, y1=0, x2=100, y2=100, confidence=0.123456789)
        ],
    )
    det = result.to_dict()["no_helmet_detections"][0]
    assert det["confidence"] == round(0.123456789, 4)


def test_detection_result_no_detections():
    result = DetectionResult(total_persons=0, persons_with_helmet=0, persons_without_helmet=0)
    d = result.to_dict()
    assert d["no_helmet_detections"] == []


# ── MockHelmDetector ──────────────────────────────────────────────────────────

def test_mock_detector_default_result():
    detector = MockHelmDetector()
    result = detector.detect("dummy_path.jpg")
    assert isinstance(result, DetectionResult)
    assert result.total_persons >= 0
    assert result.persons_with_helmet + result.persons_without_helmet == result.total_persons


def test_mock_detector_custom_result():
    custom = DetectionResult(
        total_persons=5,
        persons_with_helmet=5,
        persons_without_helmet=0,
    )
    detector = MockHelmDetector(mock_result=custom)
    result = detector.detect("any_image.jpg")
    assert result.total_persons == 5
    assert result.persons_without_helmet == 0


def test_mock_detector_image_path_irrelevant():
    detector = MockHelmDetector()
    result1 = detector.detect("img1.jpg")
    result2 = detector.detect("img2.jpg")
    assert result1.total_persons == result2.total_persons


# ── HelmDetector (without real model – ensures import error is descriptive) ──

def test_helm_detector_raises_on_missing_ultralytics(tmp_path, monkeypatch):
    """Si ultralytics no está instalado, debe lanzar ImportError descriptivo."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "ultralytics":
            raise ImportError("No module named 'ultralytics'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    model_path = str(tmp_path / "model.pt")
    # Crear el archivo para que el constructor no use mock
    open(model_path, "w").close()

    detector = HelmDetector(model_path=model_path)
    with pytest.raises(ImportError, match="ultralytics"):
        detector.detect("any.jpg")
