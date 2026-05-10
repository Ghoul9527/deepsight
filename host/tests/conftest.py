"""Pytest configuration and fixtures for DeepSight host tests."""

import sys
from pathlib import Path

import pytest

# Ensure source packages are importable
_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent.parent

sys.path.insert(0, str(_PROJECT / "shared" / "src"))
sys.path.insert(0, str(_PROJECT / "host" / "src"))
sys.path.insert(0, str(_PROJECT / "pi" / "src"))


@pytest.fixture
def sample_tracking_result():
    """Return a valid TrackingResult for reuse across tests."""
    from deepsight_host.tracking.base import TrackingResult
    return TrackingResult(
        bbox=(0.35, 0.40, 0.45, 0.52),
        center_x=0.40,
        center_y=0.46,
        confidence=0.92,
        track_id=1,
        visible=True,
        lost=False,
    )


@pytest.fixture
def lost_tracking_result():
    """Return a lost TrackingResult for safety / fallback tests."""
    from deepsight_host.tracking.base import TrackingResult
    return TrackingResult(
        bbox=(0.45, 0.45, 0.55, 0.55),
        center_x=0.5,
        center_y=0.5,
        confidence=0.0,
        track_id=-1,
        visible=False,
        lost=True,
    )
