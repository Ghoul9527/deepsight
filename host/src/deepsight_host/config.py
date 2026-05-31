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

        go = data.get("gopro", {})
        self.gopro_pi_url: str = go.get("pi_url", "http://192.168.20.51:8080")
        self.gopro_real_host: str = go.get("real_host", "172.25.132.51")

        vi = data.get("video", {})
        self.stream_url: str = vi.get("stream_url", "")

        m = data.get("mock", {})
        self.mock_enabled: bool = m.get("enabled", True)
        self.mock_video_source: str = m.get("video_source", "test_pattern")
        self.mock_video_file: str = m.get("video_file", "")
        self.mock_tracking_target: str = m.get("tracking_target", "synthetic")
        self.frame_width: int = m.get("frame_width", 1280)
        self.frame_height: int = m.get("frame_height", 720)
        self.fps: int = m.get("fps", 30)

        t = data.get("tracking", {})
        self.tracking_mode: str = t.get("mode", "fast")
        self.model_path: str = t.get("model_path", "")
        self.confidence_threshold: float = t.get("confidence_threshold", 0.5)
        self.iou_threshold: float = t.get("iou_threshold", 0.45)

        ct = data.get("controller", {})
        self.controller_poll_hz: int = ct.get("poll_hz", 50)
        self.controller_dead_zone: float = ct.get("dead_zone", 0.08)
        self.controller_smoothing_alpha: float = ct.get("smoothing_alpha", 0.4)
        self.controller_mappings: dict = ct.get("mappings", {})
        self.controller_max_winch_speed: float = ct.get("max_winch_speed", 100.0)
        self.controller_max_servo_speed: float = ct.get("max_servo_speed", 15.0)
        self.controller_sensitivity_step: float = ct.get("sensitivity_step", 0.1)
        self.controller_sensitivity_min: float = ct.get("sensitivity_min", 0.2)
        self.controller_sensitivity_max: float = ct.get("sensitivity_max", 2.0)
        if not self.controller_mappings:
            self.controller_mappings = {
                "generic": {
                    "name_patterns": [],
                    "axes": {
                        "winch": {"axis": 1, "invert": False},
                        "plate_yaw": {"axis": 0, "invert": False},
                        "gimbal_pitch": {"axis": 3, "invert": True},
                        "gimbal_yaw": {"axis": 2, "invert": False},
                        "light": {"axis": 5},
                    },
                    "buttons": {
                        "drop_to_3m": 4, "body_recenter": 8, "gimbal_recenter": 9,
                        "all_recenter": 10, "tracking": 5, "record": 1,
                        "hud": 2, "roll_recenter": 3, "preset": 0,
                        "e_stop": 6, "lock": 7,
                        "light_down": 11, "light_up": 12,
                    },
                    "dpad": {
                        "winch_sens_up": [0, 1], "winch_sens_down": [0, -1],
                        "plate_sens_left": [-1, 0], "plate_sens_right": [1, 0],
                    },
                }
            }

        c = data.get("control", {})
        self.pid_p: float = c.get("pid_p", 0.8)
        self.pid_i: float = c.get("pid_i", 0.05)
        self.pid_d: float = c.get("pid_d", 0.2)
        self.max_servo_speed: float = c.get("max_servo_speed", 15.0)
        self.dead_zone: float = c.get("dead_zone", 0.02)
        self.pos_deadband: float = c.get("pos_deadband", 0.005)
        self.out_ema_alpha: float = c.get("out_ema_alpha", 0.75)

        gi = data.get("gimbal", {})
        self.gimbal_yaw_max_angle: float = gi.get("yaw_max_angle", 15.0)
        self.gimbal_pitch_max_angle: float = gi.get("pitch_max_angle", 15.0)

        pl = data.get("plate", {})
        self.plate_max_angle: float = pl.get("max_angle", 45.0)

        s = data.get("safety", {})
        self.tracking_lost_hold_s: float = s.get("tracking_lost_hold_s", 0.5)
        self.tracking_lost_neutral_s: float = s.get("tracking_lost_neutral_s", 2.0)
        self.servo_neutral_angle: float = s.get("servo_neutral_angle", 90.0)

        lg = data.get("logging", {})
        self.log_level: str = lg.get("level", "DEBUG")
        self.log_dir: str = lg.get("dir", "logs/host/")
        self.telemetry_record: bool = lg.get("telemetry_record", False)

        dl = data.get("download", {})
        self.media_download_dir: str = dl.get(
            "media_dir", str(Path.home() / "DeepSight_Media"))

        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.media_download_dir, exist_ok=True)
