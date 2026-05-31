"""Records telemetry streams + tracking results for later replay."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from pathlib import Path

from deepsight_shared.protocol import Message

logger = logging.getLogger("host.logging.recorder")


class TelemetryRecorder:
    """Records all incoming telemetry to a time-indexed JSONL file.

    Each line: {"elapsed_s": <float>, "msg": <Message dict>}
    """

    def __init__(self, output_dir: str = "logs/telemetry/"):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._file = None
        self._start_time = 0.0
        self._path: Path | None = None
        self._entry_count = 0

    @property
    def recording(self) -> bool:
        return self._file is not None

    @property
    def current_path(self) -> Path | None:
        return self._path

    @property
    def elapsed(self) -> float:
        if self._start_time == 0.0:
            return 0.0
        return time.monotonic() - self._start_time

    @property
    def entry_count(self) -> int:
        return self._entry_count

    def start(self):
        ts = time.strftime("%Y%m%d_%H%M%S")
        self._path = self._output_dir / f"session_{ts}.jsonl"
        self._file = open(self._path, "w")
        self._start_time = time.monotonic()
        self._entry_count = 0

        # Write session header
        self._write_line({
            "type": "session_start",
            "elapsed_s": 0.0,
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        logger.info("Recording session to %s", self._path)

    def record(self, msg: Message):
        if not self._file:
            return
        entry = {
            "elapsed_s": self.elapsed,
            "msg": {
                "msg_id": msg.msg_id,
                "timestamp_ns": msg.timestamp_ns,
                "node_id": msg.node_id,
                "type": msg.type,
                "payload": msg.payload,
            },
        }
        self._write_line(entry)
        self._entry_count += 1

    def record_tracking(self, track_id: int, confidence: float,
                        center_x: float, center_y: float,
                        bbox: tuple | None = None, lost: bool = False):
        """Record a tracking result (not a network message — local to host)."""
        if not self._file:
            return
        entry = {
            "elapsed_s": self.elapsed,
            "msg": {
                "msg_id": f"track_{self._entry_count}",
                "timestamp_ns": int(time.time() * 1e9),
                "node_id": "host",
                "type": "tel.tracking_result",
                "payload": {
                    "track_id": track_id,
                    "confidence": confidence,
                    "center_x": center_x,
                    "center_y": center_y,
                    "bbox": list(bbox) if bbox else None,
                    "lost": lost,
                },
            },
        }
        self._write_line(entry)
        self._entry_count += 1

    def record_event(self, event_type: str, data: dict | None = None):
        """Record a custom session event (e.g. mode switch, e-stop, etc.)."""
        if not self._file:
            return
        entry = {
            "elapsed_s": self.elapsed,
            "msg": {
                "msg_id": f"evt_{self._entry_count}",
                "timestamp_ns": int(time.time() * 1e9),
                "node_id": "host",
                "type": event_type,
                "payload": data or {},
            },
        }
        self._write_line(entry)
        self._entry_count += 1

    def stop(self):
        if self._file:
            # Write session footer
            self._write_line({
                "type": "session_end",
                "elapsed_s": self.elapsed,
                "total_entries": self._entry_count,
            })
            self._file.close()
            self._file = None
            logger.info("Session recorded: %d entries, %.1f s → %s",
                         self._entry_count, self.elapsed, self._path)

    def _write_line(self, data: dict):
        self._file.write(json.dumps(data, default=_json_default) + "\n")


def _json_default(obj):
    """Convert numpy scalars to Python native types for JSON serialization."""
    try:
        import numpy as np
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except ImportError:
        pass
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
