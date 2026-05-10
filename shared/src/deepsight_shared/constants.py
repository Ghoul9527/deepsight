from enum import Enum


class NodeId(str, Enum):
    HOST = "host"
    PI = "pi"
    PICO = "pico"
    STM32 = "stm32"


class SafetyState(str, Enum):
    NOMINAL = "nominal"
    DEGRADED = "degraded"
    CAUTION = "caution"
    SAFE = "safe"
    EMERGENCY = "emergency"


class TrackingMode(str, Enum):
    FAST = "fast"
    PRECISE = "precise"


# Timing constants (seconds)
HEARTBEAT_INTERVAL = 0.5
HEARTBEAT_DEGRADED_TIMEOUT = 2.0
HEARTBEAT_LOST_TIMEOUT = 5.0
SERVO_SAFE_TIMEOUT = 1.0
TRACKING_LOST_HOLD = 0.5
TRACKING_LOST_NEUTRAL = 2.0

# Default ports
HOST_UDP_PORT = 5000
HOST_WS_PORT = 5001
PI_UDP_PORT = 5100
PI_WS_PORT = 5101
