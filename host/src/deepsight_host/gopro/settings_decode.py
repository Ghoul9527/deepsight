"""Generated from OpenAPI spec — maps GoPro numeric setting values to labels."""

# Key: setting ID → (title, {value: label})
SETTINGS: dict[int, tuple[str, dict[int, str]]] = {
    2: ("Resolution", {
        1: "4K", 4: "2.7K", 6: "2.7K 4:3", 7: "1440", 9: "1080",
        12: "720", 18: "4K 4:3", 21: "5.6K", 24: "5K", 25: "5K 4:3",
        26: "5.3K 8:7", 27: "5.3K 4:3", 28: "4K 8:7", 31: "8K",
        35: "5.3K 21:9", 36: "4K 21:9", 37: "4K 1:1", 38: "900",
        39: "4K SPH", 100: "5.3K", 107: "5.3K 8:7", 108: "4K 8:7",
        109: "4K 9:16", 110: "1080 9:16", 111: "2.7K 4:3",
        112: "4K 4:3", 113: "5.3K 4:3",
    }),
    3: ("FPS", {
        0: "240", 1: "120", 2: "100", 3: "60", 4: "50", 5: "48",
        6: "30", 7: "25", 8: "24", 9: "200", 10: "400",
        11: "30/25", 12: "60/50",
    }),
    5: ("Timelapse Rate", {
        0: "0.5s", 1: "1s", 2: "2s", 3: "5s", 4: "10s",
        5: "30s", 6: "60s", 7: "2min", 8: "5min",
        10: "30min", 11: "60min",
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
        0: "Wide", 2: "Narrow", 3: "Superview", 4: "Wide 4:3",
        10: "Linear", 14: "Hyperview", 15: "Superview 16:9",
        16: "Linear 16:9", 17: "Hyperview 16:9",
    }),
    122: ("Photo Lens", {
        0: "Wide 12MP", 10: "Linear 12MP", 15: "9MP Wide",
        16: "Linear 9MP", 17: "Wide 27MP", 18: "Linear 27MP",
        19: "Wide 5MP", 20: "Linear 5MP", 30: "Wide 27MP 16:9",
        31: "Linear 27MP 16:9", 32: "Wide 24.7MP",
    }),
    123: ("Timelapse Lens", {
        0: "Wide", 2: "Narrow", 3: "Superview", 19: "Narrow",
        31: "Wide 27MP", 32: "Linear 27MP",
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
        0: "Off",
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
    184: ("Profile", {0: "Standard", 1: "HDR", 2: "Log"}),
    186: ("Easy Mode", {
        0: "Highest Quality", 1: "Standard", 2: "Basic",
        3: "Ultra Slo-Mo", 4: "Basic Slo-Mo",
    }),
    187: ("Lapse Mode", {
        0: "TimeWarp", 1: "Star Trails", 2: "Light Painting",
        3: "Light Trail", 4: "Time Lapse", 5: "Night Lapse",
    }),
    189: ("Max Lens Mod", {0: "None", 1: "Max Lens 1.0", 2: "Max Lens 2.0"}),
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

# Default values for settings that GoPro omits from settingArray (factory defaults)
DEFAULTS: dict[int, int] = {
    184: 0,   # Profile → Standard
    183: 0,   # Bit Depth → 8-Bit
    182: 0,   # Bit Rate → Standard
    173: 0,   # Performance → Max Quality
    135: 0,   # Hypersmooth → Off
}

# Priority order for preset summary display
SUMMARY_ORDER = [
    # Color / Quality
    184,  # Profile (Standard/HDR/Log) — 色彩模式
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
    135, 173, 162, 189,
    # Photo
    125, 227, 122,
    # Timelapse
    5, 32, 187, 128,
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

    Checks settings 108 (Video Aspect Ratio) and 232 (Video Framing).
    Returns None if no aspect ratio setting is found.
    """
    for s in setting_array:
        sid = s.get("id", 0)
        if sid in (108, 232):
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
