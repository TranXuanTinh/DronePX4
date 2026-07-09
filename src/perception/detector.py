"""
Detector — YOLOv8 object detection using PyTorch or ONNX Runtime.

For simulation, we use standard PyTorch inference (or ONNX for CPU speed).
The interface is designed to be swappable with TensorRT on real hardware.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """Single object detection result."""
    bbox: np.ndarray         # [x1, y1, x2, y2] in pixels
    class_id: int
    class_name: str
    confidence: float

    @property
    def center(self) -> tuple[int, int]:
        """Bounding box center (x, y)."""
        return (
            int((self.bbox[0] + self.bbox[2]) / 2),
            int((self.bbox[1] + self.bbox[3]) / 2),
        )

    @property
    def area(self) -> float:
        """Bounding box area in pixels."""
        return float(
            (self.bbox[2] - self.bbox[0]) * (self.bbox[3] - self.bbox[1])
        )


class YOLODetector:
    """YOLOv8 inference using Ultralytics library.

    Supports PyTorch (.pt) and ONNX (.onnx) model formats.
    For simulation, CPU inference is sufficient for correctness testing.

    Usage:
        detector = YOLODetector(model_path="yolov8s.pt", device="cpu")
        detections = detector.detect(frame)
    """

    def __init__(
        self,
        model_path: str = "yolov8s.pt",
        device: str = "cpu",
        conf_thresh: float = 0.45,
        nms_thresh: float = 0.45,
        target_classes: Optional[List[str]] = None,
    ):
        """Initialize detector.

        Args:
            model_path: Path to YOLOv8 model file (.pt or .onnx)
            device: Inference device ("cpu" or "cuda:0")
            conf_thresh: Confidence threshold
            nms_thresh: NMS IoU threshold
            target_classes: If set, only return detections for these class names
        """
        self._model_path = model_path
        self._device = device
        self._conf_thresh = conf_thresh
        self._nms_thresh = nms_thresh
        self._target_classes = target_classes
        self._model = None
        self._inference_count = 0
        self._total_inference_time = 0.0

    def load(self) -> None:
        """Load the YOLOv8 model."""
        try:
            from ultralytics import YOLO
            logger.info(f"Loading YOLOv8 model: {self._model_path} on {self._device}")
            self._model = YOLO(self._model_path)
            logger.info(
                f"Model loaded. Classes: {list(self._model.names.values())}"
            )
        except ImportError:
            logger.error(
                "ultralytics not installed. Run: pip install ultralytics"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Run inference on a single frame.

        Args:
            frame: BGR numpy array (H, W, 3)

        Returns:
            List of Detection objects, filtered by confidence and target classes.
        """
        if self._model is None:
            raise RuntimeError("Model not loaded. Call detector.load() first.")

        start_time = time.time()

        # Run inference
        results = self._model(
            frame,
            conf=self._conf_thresh,
            iou=self._nms_thresh,
            device=self._device,
            verbose=False,
        )

        inference_time = time.time() - start_time
        self._inference_count += 1
        self._total_inference_time += inference_time

        # Parse results
        detections: List[Detection] = []

        if len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes

            for i in range(len(boxes)):
                class_id = int(boxes.cls[i].item())
                class_name = self._model.names[class_id]
                confidence = float(boxes.conf[i].item())
                bbox = boxes.xyxy[i].cpu().numpy().astype(int)

                # Filter by target classes if specified
                if self._target_classes and class_name not in self._target_classes:
                    continue

                detections.append(
                    Detection(
                        bbox=bbox,
                        class_id=class_id,
                        class_name=class_name,
                        confidence=confidence,
                    )
                )

        if detections:
            logger.debug(
                f"Detected {len(detections)} objects in {inference_time*1000:.1f}ms"
            )

        return detections

    @property
    def avg_inference_ms(self) -> float:
        """Average inference time in milliseconds."""
        if self._inference_count == 0:
            return 0.0
        return (self._total_inference_time / self._inference_count) * 1000

    @property
    def inference_count(self) -> int:
        return self._inference_count

    @property
    def class_names(self) -> dict:
        """Get model class name mapping."""
        if self._model:
            return self._model.names
        return {}
