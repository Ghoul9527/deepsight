"""Select PyTorch or native Core ML without changing tracker/control results."""
from pathlib import Path
import sys


def load_detector(model_path: str, backend: str = "auto", coreml_model_path: str = ""):
    if backend not in {"auto", "coreml"}:
        raise ValueError(f"Unknown inference backend: {backend}")
    if backend == "coreml":
        if sys.platform != "darwin":
            raise RuntimeError("Core ML requires macOS; use inference_backend: auto elsewhere")
        path = Path(coreml_model_path)
        if path.suffix != ".mlpackage" or not path.is_dir():
            raise FileNotFoundError(f"Export a Core ML model first: {path}")
        from ultralytics import YOLO
        import coremltools as ct
        # Verify native bindings early; source-only installs cannot execute Core ML.
        from coremltools.libcoremlpython import _MLModelProxy  # noqa: F401
        model = YOLO(str(path), task="detect")
        # CPU here is for Ultralytics tensor pre/postprocessing. Its Core ML backend
        # loads MLModel with ComputeUnit.ALL (OS selects CPU/GPU/Neural Engine).
        return model, "cpu", {"imgsz": 640, "rect": False}, "Core ML (ALL)"
    from ultralytics import YOLO
    import torch
    device = "cuda" if torch.cuda.is_available() else (
        "mps" if hasattr(torch.backends, "mps") and torch.backends.mps.is_available() else "cpu")
    return YOLO(model_path), device, {}, f"PyTorch ({device})"
