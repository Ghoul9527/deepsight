"""Maps tracking results to servo commands.

Converts normalized frame coordinates (0-1) to servo angles (degrees).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from deepsight_host.tracking.base import TrackingResult

logger = logging.getLogger("host.control.servo_mapper")


@dataclass
class ServoAngles:
    pan: float   # horizontal servo angle
    tilt: float  # vertical servo angle


class ServoMapper:
    def __init__(self,
                 pan_center: float = 90.0,
                 tilt_center: float = 90.0,
                 pan_range: float = 60.0,   # ± from center
                 tilt_range: float = 45.0,   # ± from center
                 invert_pan: bool = False,
                 invert_tilt: bool = False):
        self.pan_center = pan_center
        self.tilt_center = tilt_center
        self.pan_range = pan_range
        self.tilt_range = tilt_range
        self.invert_pan = invert_pan
        self.invert_tilt = invert_tilt

    def tracking_to_servo(self, result: TrackingResult) -> ServoAngles:
        if result.lost:
            # Return center for safe neutral
            return ServoAngles(pan=self.pan_center, tilt=self.tilt_center)

        # Error from center: center of frame is (0.5, 0.5)
        error_x = result.center_x - 0.5  # positive = target right of center
        error_y = result.center_y - 0.5  # positive = target below center

        if self.invert_pan:
            error_x = -error_x
        if self.invert_tilt:
            error_y = -error_y

        pan = self.pan_center + error_x * self.pan_range * 2
        tilt = self.tilt_center + error_y * self.tilt_range * 2

        pan = max(self.pan_center - self.pan_range,
                  min(self.pan_center + self.pan_range, pan))
        tilt = max(self.tilt_center - self.tilt_range,
                   min(self.tilt_center + self.tilt_range, tilt))

        return ServoAngles(pan=pan, tilt=tilt)
