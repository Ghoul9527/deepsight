"""Tracker plugin registry. Allows runtime switching between tracking modes."""

from __future__ import annotations

from typing import Type

from deepsight_host.tracking.base import TrackingEngine
from deepsight_host.tracking.fast_mode import FastModeTracker
from deepsight_host.tracking.precise_mode import PreciseModeTracker

_registry: dict[str, Type[TrackingEngine]] = {
    "fast": FastModeTracker,
    "precise": PreciseModeTracker,
}


def register_tracker(name: str, cls: Type[TrackingEngine]):
    _registry[name] = cls


def get_tracker(name: str, **kwargs) -> TrackingEngine:
    cls = _registry.get(name)
    if not cls:
        raise ValueError(f"Unknown tracker: {name}. Available: {list(_registry)}")
    return cls(**kwargs)


def list_trackers() -> list[str]:
    return list(_registry)
