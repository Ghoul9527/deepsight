"""Stream the live depth samples for one camera recording to a local file."""

import json
import logging
import math
import os
import shutil
import time
from pathlib import Path
from threading import Lock
from uuid import uuid4

from deepsight_shared.protocol import Message

logger = logging.getLogger("host.logging.depth")


class DepthRecording:
    def __init__(self):
        self._lock = Lock()
        self._file = None
        self._start_ns = 0
        self._last_flush = 0.0

    def start(self, folder: Path):
        with self._lock:
            if self._file is not None:
                return
            folder.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            path = folder / f"depth-unpaired-{stamp}-{uuid4().hex[:8]}.jsonl"
            self._start_ns = time.monotonic_ns()
            self._last_flush = time.monotonic()
            stream = path.open("x", encoding="utf-8")
            try:
                stream.write(json.dumps({"type": "start", "schema": "deepsight-depth-v1",
                                         "started_at_unix_ns": time.time_ns()}) + "\n")
                stream.flush()
            except OSError:
                stream.close()
                raise
            self._file = stream

    def sample(self, msg: Message):
        with self._lock:
            if self._file is None:
                return
            depth = float(msg.payload["depth_m"])
            if math.isfinite(depth):
                entry = {"type": "depth", "elapsed_s":
                         (time.monotonic_ns() - self._start_ns) / 1e9,
                         "depth_m": depth, "source": msg.node_id,
                         "source_timestamp_ns": msg.timestamp_ns}
                temperature = msg.payload.get("temperature_c")
                if isinstance(temperature, (int, float)) and math.isfinite(temperature):
                    entry["temperature_c"] = temperature
                self._write(entry)
                now = time.monotonic()
                if now - self._last_flush >= 1:
                    self._file.flush()
                    self._last_flush = now

    def stop(self) -> Path | None:
        with self._lock:
            stream, self._file = self._file, None
            if stream is not None:
                try:
                    stream.write(json.dumps({"type": "stop", "stopped_at_unix_ns":
                                             time.time_ns()}) + "\n")
                finally:
                    stream.close()
                return Path(stream.name)
        return None

    @staticmethod
    def finalize(path: Path, videos: list[tuple[str, str, int]]) -> Path:
        with path.open("a", encoding="utf-8") as output:
            output.write(json.dumps({"type": "media", "gopro_candidates": videos}) + "\n")
        if len(videos) != 1:
            return path
        filename = videos[0][1]
        if Path(filename).name != filename or Path(filename).suffix.lower() != ".mp4":
            return path
        target = path.with_name(Path(filename).stem + ".jsonl")
        try:
            # Exclusive creation also works on volumes without hard links.
            with path.open("rb") as source, target.open("xb") as dest:
                try:
                    shutil.copyfileobj(source, dest)
                    dest.flush()
                    os.fsync(dest.fileno())
                except OSError:
                    dest.close()
                    target.unlink(missing_ok=True)
                    raise
        except OSError as exc:
            logger.warning("Keeping depth file at %s: %s", path, exc)
            return path
        path.unlink()
        return target

    def _write(self, entry: dict):
        self._file.write(json.dumps(entry, allow_nan=False) + "\n")
