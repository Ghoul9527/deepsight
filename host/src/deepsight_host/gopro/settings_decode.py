"""MISSION 1 PRO setting labels from the Open GoPro HTTP specification."""

# Key: setting ID → (title, {value: label})
SETTINGS: dict[int, tuple[str, dict[int, str]]] = {
    2: ("Resolution", {
        1: "4K", 4: "2.7K", 6: "2.7K 4:3", 7: "1440", 9: "1080",
        12: "720", 18: "4K 4:3", 21: "5.6K", 24: "5K", 25: "5K 4:3",
        26: "5.3K 8:7", 27: "5.3K 4:3", 28: "4K 8:7", 31: "8K",
        35: "5.3K 21:9", 36: "4K 21:9", 37: "4K 1:1", 38: "900",
        39: "4K SPH", 40: "8K 4:3", 44: "1440 4:3", 100: "5.3K",
        107: "5.3K 8:7", 108: "4K 8:7",
        109: "4K 9:16", 110: "1080 9:16", 111: "2.7K 4:3",
        112: "4K 4:3", 113: "5.3K 4:3",
    }),
    3: ("FPS", {
        0: "240", 1: "120", 2: "100", 3: "90", 5: "60", 6: "50",
        8: "30", 9: "25", 10: "24", 13: "200", 15: "400",
        16: "360", 17: "300", 18: "480", 19: "960", 20: "800",
    }),
    5: ("Timelapse Rate", {
        0: "0.5s", 1: "1s", 2: "2s", 3: "5s", 4: "10s",
        5: "30s", 6: "60s", 7: "2min", 8: "5min", 9: "30min",
        10: "60min", 11: "3s", 12: "4s", 13: "15s", 14: "20s",
        15: "Auto",
    }),
    32: ("Nightlapse Rate", {
        4: "4s", 5: "5s", 10: "10s", 11: "15s", 12: "20s",
        13: "30s", 1: "60s", 2: "2min", 3: "5min",
        6: "30min", 7: "60min",
    }),
    43: ("Webcam Lens", {0: "Wide", 2: "Narrow", 3: "Superview"}),
    108: ("Aspect Ratio", {
        0: "4:3", 1: "16:9", 3: "8:7", 4: "9:16", 5: "21:9", 6: "1:1",
    }),
    111: ("Timelapse Lens", {
        0: "Wide", 2: "Narrow", 3: "Superview", 4: "Wide 4:3",
        10: "Linear", 19: "Narrow", 31: "Wide 27MP", 32: "Linear 27MP",
    }),
    121: ("Video Lens", {
        0: "Wide", 2: "Narrow", 3: "Superview",
        4: "Linear", 7: "Max SuperView", 8: "Linear + Horizon Leveling",
        9: "HyperView", 10: "Linear + Horizon Lock", 11: "Max HyperView",
        12: "Ultra SuperView", 13: "Ultra Wide", 14: "Ultra Linear",
        104: "Ultra HyperView",
    }),
    122: ("Photo Lens", {
        0: "Wide 12MP", 10: "Linear 12MP", 15: "9MP Wide",
        19: "Narrow", 27: "Wide 23MP", 28: "Linear 23MP",
        31: "Wide 27MP", 32: "Linear 27MP", 37: "9MP Linear",
        38: "13MP Linear", 39: "13MP Wide", 40: "13MP Ultra Wide",
        41: "Ultra Wide 12MP", 44: "13MP Ultra Linear",
        100: "Max SuperView", 101: "Wide", 102: "Linear",
    }),
    123: ("Timelapse Lens", {
        19: "Narrow", 31: "Wide 27MP", 32: "Linear 27MP",
        100: "Max SuperView", 101: "Wide", 102: "Linear",
    }),
    125: ("Photo Output", {0: "Standard", 1: "Raw", 2: "HDR"}),
    128: ("Media Format", {
        13: "Time Lapse Video", 20: "Time Lapse Photo", 21: "Night Lapse Photo",
    }),
    135: ("Hypersmooth", {0: "Off", 1: "Low", 2: "High", 3: "Boost", 4: "Auto Boost"}),
    150: ("Horizon Level", {0: "Off", 2: "Locked"}),
    156: ("Duration", {
        1: "15s", 2: "30s", 3: "1min", 4: "5min", 5: "15min",
        6: "30min", 7: "1hr", 8: "2hr", 9: "3hr", 10: "MAX",
        0: "Off", 11: "10s", 100: "No Limit",
    }),
    162: ("Max Lens", {0: "Off", 1: "On"}),
    173: ("Performance", {
        0: "Max Quality", 1: "Extended Battery", 2: "Tripod/Stationary",
    }),
    176: ("Easy Speed", {
        0: "8X Ultra Slo-Mo", 1: "4X Super Slo-Mo", 2: "2X Slo-Mo",
        3: "1X Speed", 4: "2X Speed", 5: "4X Speed", 6: "8X Speed",
    }),
    180: ("System Video", {
        0: "Highest Quality", 101: "Extended Battery", 102: "Longest Battery",
    }),
    182: ("Bit Rate", {0: "Standard", 1: "High", 2: "Max"}),
    183: ("Bit Depth", {0: "8-Bit", 2: "10-Bit"}),
    239: ("Sub Mode", {
        12: "Standard", 13: "Stationary", 15: "Looping", 16: "Photo",
        19: "Burst", 24: "Motion", 27: "Slo-Mo", 29: "Star Trails",
        30: "Light Painting", 31: "Vehicle Lights", 32: "Burst Slo-Mo",
        36: "Low Light", 100: "Interval",
    }),
    256: ("Image Tuning", {0: "Dive", 1: "Face", 2: "Sport", 3: "Balanced"}),
    257: ("Subject Tracking", {0: "Off", 1: "On"}),
    273: ("Output", {0: "Video", 1: "Video + JPG", 2: "Video + JPG + RAW"}),
    186: ("Easy Mode", {
        0: "Highest Quality", 1: "Standard", 2: "Basic",
        3: "Ultra Slo-Mo", 4: "Basic Slo-Mo",
    }),
    187: ("Lapse Mode", {
        0: "TimeWarp", 1: "Star Trails", 2: "Light Painting",
        3: "Light Trail", 4: "Time Lapse", 5: "Night Lapse",
    }),
    189: ("Lens Mod", {
        0: "None", 1: "Max Lens 1.0", 2: "Max Lens 2.0",
        3: "Max Lens 2.5", 4: "Macro", 5: "Anamorphic", 6: "ND 4",
        7: "ND 8", 8: "ND 16", 9: "ND 32", 10: "Standard Lens",
        11: "ND 64", 100: "Auto Detect",
    }),
    192: ("Aspect Ratio", {0: "4:3", 1: "16:9", 3: "8:7"}),
    193: ("Framing", {
        0: "Widescreen", 1: "Vertical", 2: "Full Frame",
        3: "Portrait", 5: "Vertical 9:16", 6: "16:9 Crop",
    }),
    194: ("Camera Mode", {0: "Single Lens", 1: "360"}),
    227: ("Photo Mode", {0: "SuperPhoto", 1: "Night Photo", 2: "Burst"}),
    232: ("Framing", {0: "4:3", 1: "16:9", 3: "8:7"}),
    234: ("Frame Rate", {
        0: "240", 1: "120", 2: "100", 3: "60", 4: "50", 5: "48",
        6: "30", 7: "25", 8: "24", 9: "200", 10: "400",
    }),
}

# Do not infer omitted values: MISSION capabilities and preset contents are
# context-sensitive and remain the source of truth.
DEFAULTS: dict[int, int] = {}

# Priority order for preset summary display
SUMMARY_ORDER = [
    # Color / Quality
    239, 256,  # General sub-mode and MISSION image tuning
    # Resolution
    2, 234, 3,  # Resolution, Frame Rate
    # Lens
    121,
    # Aspect Ratio
    108, 232, 192,
    # Bit Depth — 位深
    183,
    # Bit Rate
    182,
    # Other
    135, 257, 189,
    # Photo
    125, 273, 122,
    # Timelapse
    5,
]


def decode_setting(setting_id: int, value: int) -> str | None:
    """Decode a single setting value to a human-readable label."""
    info = SETTINGS.get(setting_id)
    if info is None:
        return None
    _, values = info
    return values.get(value)


# Aspect ratio setting IDs → (w, h) tuples
_ASPECT_RATIOS: dict[int, tuple[int, int]] = {
    0: (4, 3),     # 4:3
    1: (16, 9),    # 16:9
    3: (8, 7),     # 8:7
    4: (9, 16),    # 9:16
    5: (21, 9),    # 21:9
    6: (1, 1),     # 1:1
}


def preset_aspect_ratio(setting_array: list[dict]) -> tuple[int, int] | None:
    """Extract target aspect ratio (w, h) from a preset's settingArray.

    Checks settings 108 (Video Aspect Ratio) and 192 (Multi Shot Aspect Ratio).
    Returns None if no aspect ratio setting is found.
    """
    for s in setting_array:
        sid = s.get("id", 0)
        if sid in (108, 192):
            val = s.get("value", 0)
            if val in _ASPECT_RATIOS:
                return _ASPECT_RATIOS[val]
    return None


def preset_summary(setting_array: list[dict], max_items: int = 6) -> str:
    """Generate a human-readable summary line from a preset's settingArray.

    Returns something like: "Standard · 5.3K · 60 · Wide · 16:9 · 8-Bit"
    """
    decoded: dict[int, str] = {}

    # Apply defaults first (will be overridden by actual values)
    for sid, default_val in DEFAULTS.items():
        label = decode_setting(sid, default_val)
        if label:
            decoded[sid] = label

    # Override with actual settings from the preset
    for s in setting_array:
        sid = s.get("id", 0)
        val = s.get("value", 0)
        label = decode_setting(sid, val)
        if label:
            decoded[sid] = label

    parts = []
    for sid in SUMMARY_ORDER:
        if sid in decoded and decoded[sid] not in parts:
            parts.append(decoded[sid])
            if len(parts) >= max_items:
                break

    return " · ".join(parts) if parts else ""
