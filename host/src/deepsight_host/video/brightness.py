"""Display-referred image brightness; not a physical illuminance reading."""
import numpy as np


def average_brightness_pct(frame: np.ndarray) -> float:
    """Mean BGR luma of the camera preview, on a 0–100% scale."""
    means = frame.mean(axis=(0, 1), dtype=np.float64)
    return float(np.clip(np.dot(means[:3], [0.114, 0.587, 0.299]) / 255 * 100, 0, 100))
