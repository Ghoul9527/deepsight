"""OTA firmware sender for Pico — runs on Pi.

Reads local .py files, chunks them over USB CDC to the Pico,
waits for ACKs, and triggers atomic commit + reset.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import os
import time

from deepsight_pi.bridge.pico_link import PicoLink
from deepsight_shared.protocol import ota_begin, ota_chunk, ota_commit

logger = logging.getLogger("pi.ota")

CHUNK_SIZE = 512
ACK_TIMEOUT = 5.0


class OTASender:
    def __init__(self, pico_link: PicoLink):
        self._pico = pico_link

    async def execute(self, file_paths: list[str]) -> bool:
        manifest = []
        for path in file_paths:
            if not os.path.isfile(path):
                logger.error("File not found: %s", path)
                return False
            data = open(path, "rb").read()
            sha = hashlib.sha256(data).hexdigest()
            manifest.append({
                "name": os.path.basename(path),
                "size": len(data),
                "sha256": sha,
                "_data": data,
            })
            logger.info("OTA file: %s size=%d sha256=%s",
                         os.path.basename(path), len(data), sha[:16])

        logger.info("Starting OTA session: %d files", len(manifest))

        # Phase 1: begin
        begin_msg = ota_begin("pi", [
            {"name": m["name"], "size": m["size"], "sha256": m["sha256"]}
            for m in manifest
        ])
        await self._pico.send(begin_msg)
        ack = await self._wait_ack("begin", ACK_TIMEOUT)
        if ack is None:
            logger.error("OTA begin: no ACK")
            return False
        if not ack.get("ok"):
            logger.error("OTA begin rejected: %s", ack.get("error", "unknown"))
            return False
        logger.info("OTA begin accepted: %d files", ack.get("files", 0))

        # Phase 2: send chunks
        for finfo in manifest:
            fname = finfo["name"]
            data = finfo["_data"]
            total_chunks = (len(data) + CHUNK_SIZE - 1) // CHUNK_SIZE
            for seq in range(total_chunks):
                offset = seq * CHUNK_SIZE
                chunk = data[offset:offset + CHUNK_SIZE]
                b64 = base64.b64encode(chunk).decode("ascii")
                is_last = (seq == total_chunks - 1)
                msg = ota_chunk("pi", fname, seq, b64, last=is_last)
                await self._pico.send(msg)
                ack = await self._wait_ack("chunk", ACK_TIMEOUT)
                if ack is None:
                    logger.error("OTA chunk %s#%d: no ACK", fname, seq)
                    return False
                if not ack.get("ok"):
                    logger.error("OTA chunk %s#%d rejected: %s",
                                 fname, seq, ack.get("error", "unknown"))
                    return False
            logger.info("OTA file sent: %s (%d chunks)", fname, total_chunks)

        # Phase 3: commit
        commit_msg = ota_commit("pi")
        await self._pico.send(commit_msg)
        ack = await self._wait_ack("commit", ACK_TIMEOUT)
        if ack is None:
            logger.error("OTA commit: no ACK")
            return False
        if not ack.get("ok"):
            errors = ack.get("errors", ["unknown"])
            logger.error("OTA commit rejected: %s", ", ".join(errors))
            return False
        logger.info("OTA commit accepted — Pico will reset now")
        return True

    async def _wait_ack(self, step: str, timeout: float) -> dict | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                msg = await asyncio.wait_for(
                    self._pico.recv_queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            if msg.type == "ota.ack":
                p = msg.payload
                if p.get("step") == step:
                    return p
                logger.debug("OTA ack for wrong step: %s (waiting for %s)",
                             p.get("step"), step)
        return None
