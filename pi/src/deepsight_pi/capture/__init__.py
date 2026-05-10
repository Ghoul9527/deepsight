"""HDMI capture device — factory + implementations."""

from __future__ import annotations

from deepsight_pi.capture.base import CaptureDevice
from deepsight_pi.capture.mock_capture import MockCapture
from deepsight_pi.capture.real_capture import RealCapture


def create_capture(mock: bool = True, width: int = 1920, height: int = 1080,
                   fps: int = 60, device: str = "/dev/video0") -> CaptureDevice:
    if mock:
        return MockCapture(width, height, fps)
    return RealCapture(device, width, height, fps)
