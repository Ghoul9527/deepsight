"""Nominal calibration from the installed 12V positional-servo specification.

Wire commands retain 90 degrees as neutral for compatibility. Their offset from
90 now denotes physical degrees, rather than a generic 180-degree servo scale.
"""
import math

DEFAULT_CALIBRATION = {
    'pulse_min_us': 500.0,
    'pulse_neutral_us': 1500.0,
    'pulse_max_us': 2500.0,
    'physical_min_deg': -175.0,
    'physical_max_deg': 175.0,
    'neutral_command_deg': 90.0,
}
DEFAULT_DEFLECTION_LIMITS = {0:15.0, 1:15.0, 2:15.0, 3:45.0, 4:45.0}


def calibrated_pulse(angle, calibration, max_deflection):
    c={**DEFAULT_CALIBRATION, **calibration}
    if not all(math.isfinite(float(v)) for v in [angle,max_deflection,*c.values()]):
        raise ValueError('Non-finite servo command/calibration')
    low,neutral,high=(c[k] for k in ('pulse_min_us','pulse_neutral_us','pulse_max_us'))
    left,right=c['physical_min_deg'],c['physical_max_deg']
    if not (500<=low<neutral<high<=2500 and left<0<right and
            0<max_deflection<=min(-left,right)):
        raise ValueError('Invalid servo calibration or deflection limit')
    delta=max(-max_deflection,min(max_deflection,angle-c['neutral_command_deg']))
    if delta>=0:
        return neutral+delta/right*(high-neutral)
    return neutral+delta/(-left)*(neutral-low)
