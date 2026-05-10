from __future__ import annotations

import os
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path("configs/host_config.yaml")


class HostConfig:
    def __init__(self, path: Path | None = None):
        path = path or DEFAULT_CONFIG_PATH
        with open(path) as f:
            data = yaml.safe_load(f)

        h = data.get("host", {})
        self.host_id: str = h.get("id", "host")
        self.udp_port: int = h.get("udp_port", 5000)
        self.ws_port: int = h.get("ws_port", 5001)

        n = data.get("network", {})
        self.pi_address: str = n.get("pi_address", "127.0.0.1")
        self.pi_udp_port: int = n.get("pi_udp_port", 5100)
        self.pi_ws_port: int = n.get("pi_ws_port", 5101)

        vi = data.get("video", {})
        self.stream_url: str = vi.get("stream_url", "")

        m = data.get("mock", {})
        self.mock_enabled: bool = m.get("enabled", True)
        self.mock_video_source: str = m.get("video_source", "test_pattern")
        self.mock_tracking_target: str = m.get("tracking_target", "synthetic")
        self.frame_width: int = m.get("frame_width", 1280)
        self.frame_height: int = m.get("frame_height", 720)
        self.fps: int = m.get("fps", 30)

        t = data.get("tracking", {})
        self.tracking_mode: str = t.get("mode", "fast")
        self.model_path: str = t.get("model_path", "")
        self.confidence_threshold: float = t.get("confidence_threshold", 0.5)
        self.iou_threshold: float = t.get("iou_threshold", 0.45)

        c = data.get("control", {})
        self.pid_p: float = c.get("pid_p", 0.8)
        self.pid_i: float = c.get("pid_i", 0.05)
        self.pid_d: float = c.get("pid_d", 0.2)
        self.max_servo_speed: float = c.get("max_servo_speed", 60.0)
        self.dead_zone: float = c.get("dead_zone", 0.02)

        s = data.get("safety", {})
        self.tracking_lost_hold_s: float = s.get("tracking_lost_hold_s", 0.5)
        self.tracking_lost_neutral_s: float = s.get("tracking_lost_neutral_s", 2.0)
        self.servo_neutral_angle: float = s.get("servo_neutral_angle", 90.0)

        lg = data.get("logging", {})
        self.log_level: str = lg.get("level", "DEBUG")
        self.log_dir: str = lg.get("dir", "logs/host/")
        self.telemetry_record: bool = lg.get("telemetry_record", False)

        os.makedirs(self.log_dir, exist_ok=True)
