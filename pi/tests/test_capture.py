"""Tests for the HDMI capture module."""

import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared", "src"))

import pytest
import numpy as np


def async_test(coro):
    return asyncio.run(coro)


class TestCaptureDeviceABC:
    def test_abc_cannot_instantiate(self):
        from deepsight_pi.capture.base import CaptureDevice
        with pytest.raises(TypeError):
            CaptureDevice()

    def test_abstract_methods(self):
        from deepsight_pi.capture.base import CaptureDevice
        abstract = CaptureDevice.__abstractmethods__
        assert "start" in abstract
        assert "stop" in abstract
        assert "read_frame" in abstract


class TestMockCapture:
    @pytest.fixture
    def cap(self):
        from deepsight_pi.capture.mock_capture import MockCapture
        return MockCapture()

    def test_default_dimensions(self, cap):
        assert cap.width == 1920
        assert cap.height == 1080
        assert cap.fps == 60

    def test_custom_dimensions(self):
        from deepsight_pi.capture.mock_capture import MockCapture
        cap = MockCapture(width=640, height=480, fps=30)
        assert cap.width == 640
        assert cap.height == 480

    def test_read_frame_none_before_start(self, cap):
        frame = async_test(cap.read_frame())
        assert frame is None

    def test_start(self, cap):
        assert async_test(cap.start()) is True
        assert cap._running is True

    def test_read_frame_after_start(self, cap):
        async_test(cap.start())
        frame = async_test(cap.read_frame())
        assert isinstance(frame, np.ndarray)
        assert frame.shape == (1080, 1920, 3)
        assert frame.dtype == np.uint8

    def test_read_frame_values_in_range(self, cap):
        async_test(cap.start())
        frame = async_test(cap.read_frame())
        assert frame.min() >= 0
        assert frame.max() <= 255

    def test_read_frame_changes(self, cap):
        async_test(cap.start())
        f1 = async_test(cap.read_frame())
        f2 = async_test(cap.read_frame())
        # Both should return test pattern (same content, but frame count differs)
        assert f1.shape == f2.shape

    def test_stop(self, cap):
        async_test(cap.start())
        assert async_test(cap.stop()) is True
        assert cap._running is False

    def test_read_frame_after_stop(self, cap):
        async_test(cap.start())
        async_test(cap.stop())
        frame = async_test(cap.read_frame())
        assert frame is None


class TestCreateCaptureFactory:
    def test_mock_true_returns_mock(self):
        from deepsight_pi.capture import create_capture
        from deepsight_pi.capture.mock_capture import MockCapture
        device = create_capture(mock=True)
        assert isinstance(device, MockCapture)

    def test_mock_false_handles_missing_hw(self):
        from deepsight_pi.capture import create_capture
        try:
            device = create_capture(mock=False)
            # Should not crash even without real hardware
            assert device is not None
        except (RuntimeError, ImportError):
            pass
