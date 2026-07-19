"""
Detector — YOLOv8 implementation of ObjectDetector.

For simulation, uses standard PyTorch inference (or ONNX for CPU speed).
The ObjectDetector interface allows swapping with TensorRT on real hardware.
"""
from __future__ import annotations

import logging
import time
from typing import List, Optional

import cv2
import numpy as np

from src.core.interfaces import ObjectDetector
from src.core.types import Detection

logger = logging.getLogger(__name__)


class YOLODetector(ObjectDetector):
    """YOLOv8 inference using Ultralytics library.

    Implements the ObjectDetector interface. Supports PyTorch (.pt)
    and ONNX (.onnx) model formats.

    Usage:
        detector = YOLODetector(model_path="yolov8s.pt", device="cpu")
        detector.load()
        detections = detector.detect(frame)
    """

    def __init__(
        self,
        model_path: str = "yolov8s.pt",
        device: str = "cpu",
        conf_thresh: float = 0.45,
        nms_thresh: float = 0.45,
        target_classes: Optional[List[str]] = None,
    ) -> None:
        self._model_path = model_path
        self._device = device
        self._conf_thresh = conf_thresh
        self._nms_thresh = nms_thresh
        self._target_classes = target_classes
        self._model = None
        self._inference_count = 0
        self._total_inference_time = 0.0

    # ── ObjectDetector interface ─────────────────────────────

    def load(self) -> None:
        try:
            import torch
            cuda_working = False
            if torch.cuda.is_available():
                try:
                    # Allocate a small conv layer and run it on CUDA to verify compute capability support
                    conv = torch.nn.Conv2d(1, 1, 1).cuda()
                    x = torch.zeros(1, 1, 1, 1).cuda()
                    _ = conv(x)
                    cuda_working = True
                except Exception as e:
                    logger.warning(
                        f"CUDA device found but test convolution failed: {e}. "
                        "This indicates PyTorch does not support your GPU's older compute capability (sm_52). "
                        "Running YOLOv8 on CPU fallback."
                    )

            if "cuda" in str(self._device).lower():
                if not cuda_working:
                    logger.warning("CUDA is not working/compatible. Falling back to CPU.")
                    self._device = "cpu"
                else:
                    logger.info("CUDA is working and will be used for YOLO inference.")
            elif self._device == "cpu" or self._device is None:
                if cuda_working:
                    logger.info("CUDA is working. Automatically using GPU for YOLO inference.")
                    self._device = "cuda"

            if self._device == "cpu":
                try:
                    # Limit CPU threads to prevent pegging all CPU cores at 100%
                    torch.set_num_threads(2)
                    logger.info("Limiting PyTorch CPU threads to 2 to maintain system responsiveness.")
                except Exception as e:
                    logger.warning(f"Could not limit PyTorch CPU thread count: {e}")

            from ultralytics import YOLO
            logger.info(
                f"Loading YOLOv8 model: {self._model_path} "
                f"on {self._device}"
            )
            self._model = YOLO(self._model_path)
            try:
                self._model.to(self._device)
            except Exception as e:
                logger.warning(f"Failed to move model to {self._device}: {e}. Running on default device.")
            logger.info(
                f"Model loaded. Classes: "
                f"{list(self._model.names.values())}"
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
        if self._model is None:
            raise RuntimeError(
                "Model not loaded. Call detector.load() first."
            )

        start_time = time.monotonic()

        results = self._model(
            frame,
            conf=self._conf_thresh,
            iou=self._nms_thresh,
            device=self._device,
            verbose=False,
        )

        inference_time = time.monotonic() - start_time
        self._inference_count += 1
        self._total_inference_time += inference_time

        detections: List[Detection] = []

        if len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes
            for i in range(len(boxes)):
                class_id = int(boxes.cls[i].item())
                class_name = self._model.names[class_id]
                confidence = float(boxes.conf[i].item())
                bbox = boxes.xyxy[i].cpu().numpy().astype(int)

                if (self._target_classes
                        and class_name not in self._target_classes):
                    continue

                detections.append(Detection(
                    bbox=bbox,
                    class_id=class_id,
                    class_name=class_name,
                    confidence=confidence,
                ))

        if detections:
            logger.debug(
                f"Detected {len(detections)} objects "
                f"in {inference_time * 1000:.1f}ms"
            )

        return detections

    @property
    def avg_inference_ms(self) -> float:
        if self._inference_count == 0:
            return 0.0
        return (self._total_inference_time / self._inference_count) * 1000

    # ── Extra accessors ──────────────────────────────────────

    @property
    def inference_count(self) -> int:
        return self._inference_count

    @property
    def class_names(self) -> dict:
        if self._model:
            return self._model.names
        return {}
