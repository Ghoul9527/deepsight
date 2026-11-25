"""Map preview brightness inversely to fill-light PWM."""
import math


def next_light_percent(image_percent: float, current_pwm: float,
                       image_at_zero: float = 20.0,
                       image_at_full: float = 0.0) -> float:
    """Linear inverse mapping, clamped at both configured endpoints."""
    if not all(math.isfinite(v) for v in (image_percent, image_at_zero, image_at_full)):
        return current_pwm
    if not 0 <= image_at_full < image_at_zero <= 100:
        raise ValueError('The image brightness at 0% PWM must exceed that at 100% PWM')
    return round(max(0.0, min(100.0,
        (image_at_zero - image_percent) / (image_at_zero - image_at_full) * 100)), 1)
