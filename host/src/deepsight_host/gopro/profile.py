"""Camera profile and compatibility helpers for GoPro MISSION 1 PRO."""

from __future__ import annotations

from dataclasses import dataclass
import re


MISSION_1_PRO_MODEL = "Mission 1 Pro"
MISSION_1_PRO_MIN_OPEN_GOPRO_FIRMWARE = "1.10.00"
MISSION_1_PRO_LABS_FIRMWARE = "2.02.70"

GENERAL_PRESET_GROUP = 2000
LEGACY_PRESET_GROUPS = {
    "video": 1000,
    "photo": 1001,
    "timelapse": 1002,
}

# MISSION cameras expose top-level modes as presets in the GENERAL group.
# Prefer the canonical mode first, then accept mode-specific variants.
CAPTURE_MODE_IDS: dict[str, tuple[int, ...]] = {
    "video": (12, 15, 27, 32, 36),
    "photo": (17, 16, 18, 19),
    "timelapse": (13, 24, 20, 21, 26, 29, 30, 31),
}


def normalize_model_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def is_mission_1_pro(value: object) -> bool:
    return normalize_model_name(value) in {"mission1pro", "gopromission1pro"}


def firmware_version_tuple(value: object) -> tuple[int, ...]:
    """Extract the final semantic version from a camera firmware string."""
    parts = re.findall(r"\d+", str(value))
    return tuple(int(part) for part in parts[-3:]) if len(parts) >= 3 else ()


@dataclass(frozen=True)
class CameraCompatibility:
    model_name: str
    firmware_version: str
    open_gopro_version: str
    capabilities_schema: str
    supports_two_byte_ids: bool
    model_supported: bool
    open_gopro_supported: bool
    labs_version_current: bool

    @property
    def ready(self) -> bool:
        return self.model_supported and self.open_gopro_supported
