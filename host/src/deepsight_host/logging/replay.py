"""Replay recorded telemetry sessions with seek and speed control."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from deepsight_shared.protocol import Message

logger = logging.getLogger("host.logging.replay")


class ReplayEngine:
    """Loads a JSONL session file and replays messages in time order.

    Supports play, pause, seek, and speed multiplier.
    """

    def __init__(self, file_path: str = ""):
        self._path = Path(file_path) if file_path else None
        self._entries: list[dict] = []
        self._index = 0
        self._speed = 1.0
        self._playing = False
        self._duration = 0.0

    # ── Properties ──

    @property
    def loaded(self) -> bool:
        return len(self._entries) > 0

    @property
    def playing(self) -> bool:
        return self._playing

    @property
    def progress(self) -> float:
        if not self._entries:
            return 0.0
        return self._index / len(self._entries)

    @property
    def duration(self) -> float:
        return self._duration

    @property
    def index(self) -> int:
        return self._index

    @property
    def total_entries(self) -> int:
        return len(self._entries)

    @property
    def speed(self) -> float:
        return self._speed

    @speed.setter
    def speed(self, value: float):
        self._speed = max(0.1, min(10.0, value))

    # ── Operations ──

    def load(self, file_path: str = ""):
        if file_path:
            self._path = Path(file_path)
        if self._path is None:
            return

        self._entries.clear()
        self._index = 0
        with open(self._path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    self._entries.append(entry)
                except json.JSONDecodeError:
                    continue

        if self._entries:
            self._duration = self._entries[-1].get("elapsed_s", 0.0)

        logger.info("Loaded %d entries (%.1f s) from %s",
                     len(self._entries), self._duration, self._path)

    def play(self):
        self._playing = True

    def pause(self):
        self._playing = False

    def stop(self):
        self._playing = False
        self._index = 0

    def seek(self, elapsed_s: float):
        """Jump to the closest entry at or before *elapsed_s*."""
        lo, hi = 0, len(self._entries) - 1
        target = 0
        while lo <= hi:
            mid = (lo + hi) // 2
            t = self._entries[mid].get("elapsed_s", 0.0)
            if t <= elapsed_s:
                target = mid
                lo = mid + 1
            else:
                hi = mid - 1
        self._index = target

    def seek_pct(self, pct: float):
        """Seek to *pct* (0.0–1.0) of total duration."""
        self.seek(max(0.0, min(1.0, pct)) * self._duration)

    def next_message(self, dt_s: float) -> Message | None:
        """Advance by *dt_s* (scaled by speed) and return the next message if due.

        Returns None if no message is due this tick, or if at end of stream.
        """
        if not self._playing or self._index >= len(self._entries):
            return None

        entry = self._entries[self._index]
        entry_time = entry.get("elapsed_s", 0.0)

        # Check if this entry is due
        current_time = entry_time  # we use the entry's own timestamp

        self._index += 1

        # Skip non-message entries (session_start, session_end)
        if "msg" not in entry:
            return self.next_message(dt_s)

        raw = entry["msg"]
        try:
            return Message.from_json(json.dumps(raw))
        except Exception as e:
            logger.debug("Replay parse error: %s", e)
            return self.next_message(dt_s)

    def get_all_messages_up_to(self, elapsed_s: float) -> list[Message]:
        """Return all messages within [last_read_time, elapsed_s]. Used for batch replay."""
        msgs = []
        while self._index < len(self._entries):
            entry = self._entries[self._index]
            if entry.get("elapsed_s", 0.0) > elapsed_s:
                break
            self._index += 1
            if "msg" not in entry:
                continue
            raw = entry["msg"]
            try:
                msgs.append(Message.from_json(json.dumps(raw)))
            except Exception:
                continue
        return msgs

    def reset(self):
        self._index = 0
        self._playing = False
