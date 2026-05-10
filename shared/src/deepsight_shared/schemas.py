"""JSON Schema definitions for all message types.

These schemas can be used for validation and documentation generation.
"""

MESSAGE_ENVELOPE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Message",
    "type": "object",
    "required": ["msg_id", "timestamp_ns", "node_id", "type", "version"],
    "properties": {
        "msg_id": {"type": "string"},
        "timestamp_ns": {"type": "integer"},
        "node_id": {"type": "string", "enum": ["host", "pi", "pico", "stm32"]},
        "type": {"type": "string"},
        "version": {"type": "string"},
        "payload": {"type": "object"},
    },
}

SERVO_COMMAND_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ServoCommand",
    "type": "object",
    "required": ["servo_id", "angle"],
    "properties": {
        "servo_id": {"type": "integer", "minimum": 0, "maximum": 15},
        "angle": {"type": "number", "minimum": 0, "maximum": 180},
        "speed": {"type": "number", "default": 0.0},
    },
}

IMU_DATA_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "IMUData",
    "type": "object",
    "required": ["yaw", "pitch", "roll"],
    "properties": {
        "yaw": {"type": "number"},
        "pitch": {"type": "number"},
        "roll": {"type": "number"},
        "accel_x": {"type": "number"},
        "accel_y": {"type": "number"},
        "accel_z": {"type": "number"},
    },
}

DEPTH_DATA_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "DepthData",
    "type": "object",
    "required": ["depth_m"],
    "properties": {
        "depth_m": {"type": "number", "minimum": 0},
        "pressure_mbar": {"type": "number"},
        "temperature_c": {"type": "number"},
    },
}

TRACKING_TARGET_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "TrackingTarget",
    "type": "object",
    "required": ["x", "y", "confidence", "track_id", "visible"],
    "properties": {
        "x": {"type": "number", "minimum": 0, "maximum": 1},
        "y": {"type": "number", "minimum": 0, "maximum": 1},
        "w": {"type": "number"},
        "h": {"type": "number"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "track_id": {"type": "integer"},
        "visible": {"type": "boolean"},
    },
}

HEARTBEAT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Heartbeat",
    "type": "object",
    "required": [],
    "properties": {},
}
