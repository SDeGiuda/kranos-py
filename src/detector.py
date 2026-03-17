"""
Módulo de detección de cascos.

Utiliza un modelo YOLOv8 (ultralytics) entrenado localmente para:
  - Contar el total de personas detectadas.
  - Distinguir personas con casco (helmet_class_id) de personas sin casco
    (no_helmet_class_id).
  - Retornar las coordenadas de bounding-box de cada persona sin casco.

Si el modelo no está disponible o ultralytics no está instalado, el módulo
puede operar en modo MOCK para facilitar el desarrollo y las pruebas.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """Representa una detección individual de persona sin casco."""
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float


@dataclass
class DetectionResult:
    """Resultado completo de un análisis de imagen."""
    total_persons: int
    persons_with_helmet: int
    persons_without_helmet: int
    no_helmet_detections: List[Detection] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_persons": self.total_persons,
            "persons_with_helmet": self.persons_with_helmet,
            "persons_without_helmet": self.persons_without_helmet,
            "no_helmet_detections": [
                {
                    "x1": d.x1,
                    "y1": d.y1,
                    "x2": d.x2,
                    "y2": d.y2,
                    "confidence": round(d.confidence, 4),
                }
                for d in self.no_helmet_detections
            ],
        }


class HelmDetector:
    """Detector de cascos basado en YOLOv8."""

    def __init__(
        self,
        model_path: str,
        confidence_threshold: float = 0.50,
        helmet_class_id: int = 0,
        no_helmet_class_id: int = 1,
        imgsz: int = 640,
    ):
        """
        Args:
            model_path: Ruta al archivo de pesos del modelo (.pt).
            confidence_threshold: Confianza mínima para aceptar una detección.
            helmet_class_id: ID de clase para "persona con casco".
            no_helmet_class_id: ID de clase para "persona sin casco".
            imgsz: Tamaño de la imagen de inferencia.
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.helmet_class_id = helmet_class_id
        self.no_helmet_class_id = no_helmet_class_id
        self.imgsz = imgsz
        self._model = None

    def _load_model(self):
        """Carga el modelo YOLOv8 de forma diferida."""
        if self._model is not None:
            return
        try:
            from ultralytics import YOLO  # pylint: disable=import-outside-toplevel

            self._model = YOLO(self.model_path)
            logger.info("Modelo YOLOv8 cargado desde: %s", self.model_path)
        except ImportError as exc:
            raise ImportError(
                "El paquete 'ultralytics' no está instalado. "
                "Ejecute: pip install ultralytics"
            ) from exc

    def detect(self, image_path: str) -> DetectionResult:
        """
        Procesa una imagen y retorna el resultado de la detección.

        Args:
            image_path: Ruta a la imagen a analizar.

        Returns:
            DetectionResult con conteos y coordenadas.
        """
        self._load_model()

        results = self._model.predict(
            source=image_path,
            conf=self.confidence_threshold,
            imgsz=self.imgsz,
            verbose=False,
        )

        persons_with_helmet = 0
        persons_without_helmet = 0
        no_helmet_detections: List[Detection] = []

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())

                if cls_id == self.helmet_class_id:
                    persons_with_helmet += 1
                elif cls_id == self.no_helmet_class_id:
                    persons_without_helmet += 1
                    no_helmet_detections.append(
                        Detection(x1=x1, y1=y1, x2=x2, y2=y2, confidence=conf)
                    )

        total_persons = persons_with_helmet + persons_without_helmet

        result = DetectionResult(
            total_persons=total_persons,
            persons_with_helmet=persons_with_helmet,
            persons_without_helmet=persons_without_helmet,
            no_helmet_detections=no_helmet_detections,
        )
        logger.info(
            "Detección completada: %d personas (%d con casco, %d sin casco)",
            total_persons,
            persons_with_helmet,
            persons_without_helmet,
        )
        return result


class MockHelmDetector:
    """
    Detector simulado para pruebas y desarrollo sin hardware ni modelo.

    Retorna siempre el resultado configurado en el constructor.
    """

    def __init__(self, mock_result: Optional[DetectionResult] = None):
        self._mock_result = mock_result or DetectionResult(
            total_persons=2,
            persons_with_helmet=1,
            persons_without_helmet=1,
            no_helmet_detections=[
                Detection(x1=100, y1=150, x2=200, y2=300, confidence=0.90)
            ],
        )

    def detect(self, image_path: str) -> DetectionResult:  # noqa: D102
        logger.debug("MockHelmDetector: devolviendo resultado simulado para %s", image_path)
        return self._mock_result
