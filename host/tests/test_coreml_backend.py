import sys
from types import SimpleNamespace
import pytest
from deepsight_host.tracking.inference import load_detector


def test_coreml_requires_macos(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    with pytest.raises(RuntimeError, match="macOS"):
        load_detector("unused.pt", "coreml", "unused.mlpackage")


def test_coreml_missing_export_fails_instead_of_synthetic(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    with pytest.raises(FileNotFoundError, match="Export"):
        load_detector("unused.pt", "coreml", "missing.mlpackage")


def test_auto_preserves_pytorch_selection(monkeypatch):
    import ultralytics
    import torch
    monkeypatch.setattr(ultralytics, "YOLO", lambda path: path)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    model, device, kwargs, label = load_detector("original.pt")
    assert (model, device, kwargs) == ("original.pt", "cpu", {})
    assert label == "PyTorch (cpu)"


def test_invalid_backend_is_not_silently_accepted():
    with pytest.raises(ValueError, match="backend"):
        load_detector("unused.pt", "typo")
