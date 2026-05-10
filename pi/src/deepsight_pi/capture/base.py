from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import numpy as np

logger = logging.getLogger("pi.capture")


class CaptureDevice(ABC):
    @abstractmethod
    async def start(self) -> bool: ...
    @abstractmethod
    async def stop(self) -> bool: ...
    @abstractmethod
    async def read_frame(self) -> np.ndarray | None: ...
