from __future__ import annotations

from pathlib import Path

import yaml


class PiConfig:
    def __init__(self, path: Path | None = None):
        path = path or Path("configs/pi_config.yaml")
        with open(path) as f:
            data = yaml.safe_load(f)

        p = data.get("pi", {})
        self.pi_id: str = p.get("id", "pi")
        self.udp_port: int = p.get("udp_port", 5100)
        self.ws_port: int = p.get("ws_port", 5101)

        n = data.get("network", {})
        self.host_address: str = n.get("host_address", "127.0.0.1")
        self.host_udp_port: int = n.get("host_udp_port", 5000)
        self.host_ws_port: int = n.get("host_ws_port", 5001)

        s = data.get("serial", {})
        self.pico_port: str = s.get("pico_port", "mock")
        self.pico_telemetry_port: str = s.get("pico_telemetry_port", s.get("pico_port", "mock"))
        self.stm32_port: str = s.get("stm32_port", "mock")
        self.pico_baud: int = s.get("pico_baud", 115200)
        self.stm32_baud: int = s.get("stm32_baud", 115200)

        w = data.get("watchdog", {})
        self.heartbeat_interval_s: float = w.get("heartbeat_interval_s", 0.5)
        self.reconnect_delay_s: float = w.get("reconnect_delay_s", 2.0)

        lg = data.get("logging", {})
        self.log_level: str = lg.get("level", "DEBUG")
        self.log_dir: str = lg.get("dir", "logs/pi/")

        from pathlib import Path as _Path
        _Path(self.log_dir).mkdir(parents=True, exist_ok=True)
