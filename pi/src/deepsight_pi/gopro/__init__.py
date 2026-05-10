"""GoPro controller — factory + implementations."""

from __future__ import annotations

from deepsight_pi.gopro.base import GoProController
from deepsight_pi.gopro.mock_gopro import MockGoPro
from deepsight_pi.gopro.real_gopro import RealGoPro


def create_gopro(mock: bool = True) -> GoProController:
    if mock:
        return MockGoPro()
    return RealGoPro()
