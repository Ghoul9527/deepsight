"""GoPro USB stream manager — ViewFinder (720p) and Webcam (1080p) modes.

Receives the GoPro's internally-encoded H.264/MPEG-TS UDP stream and
feeds it to the StreamRelay for distribution to Host clients.

Two modes:
  - viewfinder: /gopro/camera/stream/start  (camera preview, lower overhead)
  - webcam:     /gopro/webcam/start         (1080p, higher quality)
"""

from __future__ import annotations

import asyncio
import logging
import time
from urllib.request import urlopen, Request

logger = logging.getLogger("pi.gopro_stream")

UDP_PORT = 8554


class GoProStreamManager:
    """Receives GoPro's UDP MPEG-TS and forwards to Host via UDP.

    Low-latency design: GoPro datagrams are forwarded directly to the Host
    over UDP — no TCP relay, no ring buffer, no extra copies. The Host runs
    ffmpeg reading udp:// directly, eliminating the TCP→pipe→ffmpeg hop.
    """

    def __init__(self, gopro_ip: str = "172.25.132.51"):
        self._gopro_ip = gopro_ip
        self._mode: str | None = None
        self._transport: asyncio.DatagramTransport | None = None
        self._reader: asyncio.StreamReader | None = None
        self._relay_task: asyncio.Task | None = None
        self._keep_alive_task: asyncio.Task | None = None
        self._health_task: asyncio.Task | None = None
        self._running = False
        self._last_data_time: float = 0.0

        # UDP forward target (Host IP, port) — direct low-latency path
        self._forward_addr: tuple[str, int] | None = None

        # PCR-based latency estimation (GoPro encoder clock → Pi system clock)
        self._pcr_first_pi: float | None = None   # Pi monotonic at first valid PCR
        self._pcr_first_val: float | None = None  # PCR seconds at first valid PCR
        self._pcr_last_pi: float = 0.0            # Pi time of last valid PCR
        self._pcr_last_val: float = 0.0           # PCR seconds of last valid PCR
        self._pcr_latency_ms: float = 0.0         # latency delta from baseline

    # ── public API ────────────────────────────────────────────

    @property
    def mode(self) -> str | None:
        return self._mode

    @property
    def running(self) -> bool:
        return self._running

    @property
    def pcr_latency_ms(self) -> float:
        """Estimated latency delta from GoPro encoder to Pi UDP receive.

        Uses MPEG-TS PCR timestamps compared against Pi system time.
        Returns change from initial conditions (ms). Negative = lower latency
        than at stream start. Add to FAQ baseline (210ms) for absolute estimate.
        """
        return self._pcr_latency_ms

    async def start_viewfinder(self, relay) -> None:
        """Start the viewfinder (720p-class) preview and relay to clients."""
        if self._running and self._transport is not None:
            if self._mode == "viewfinder":
                return
            # Switching modes — just change GoPro endpoint, keep UDP receiver
            self._start_gopro_stream("viewfinder")
            self._mode = "viewfinder"
            logger.info("Switched to viewfinder stream")
            return
        await self._start_stream("viewfinder", relay)

    async def start_webcam(self, relay) -> None:
        """Start the webcam (1080p) preview and relay to clients."""
        if self._running and self._transport is not None:
            if self._mode == "webcam":
                return
            # Switching modes — just change GoPro endpoint, keep UDP receiver
            self._start_gopro_stream("webcam")
            self._mode = "webcam"
            logger.info("Switched to webcam stream")
            return
        await self._start_stream("webcam", relay)

    async def _start_stream(self, mode: str, relay) -> None:
        """Start stream with retry on port conflict."""
        self._start_gopro_stream(mode)
        await asyncio.sleep(1.0)
        for attempt in range(3):
            try:
                await self._start_udp_receiver(relay)
                self._mode = mode
                logger.info("%s stream started (UDP:%d → relay)", mode, UDP_PORT)
                return
            except OSError as e:
                if attempt < 2:
                    logger.warning("Port %d in use, retrying in 1s...", UDP_PORT)
                    await asyncio.sleep(1.0)
                else:
                    self._running = False
                    raise RuntimeError(
                        f"Cannot bind UDP:{UDP_PORT} after 3 attempts: {e}"
                    ) from e

    async def stop(self) -> None:
        """Stop the stream and release resources."""
        await self._stop_internal()
        self._mode = None
        logger.info("GoPro stream stopped")

    def set_gopro_ip(self, ip: str) -> None:
        self._gopro_ip = ip

    def set_forward_target(self, host: str, port: int) -> None:
        """Set the Host UDP target for direct datagram forwarding.

        When set, every GoPro UDP datagram received is forwarded directly
        to this address. This is the low-latency path — no TCP relay,
        no ring buffer, no extra copies.
        """
        self._forward_addr = (host, port)
        logger.info("UDP forward target set: %s:%d", host, port)

    # ── GoPro HTTP control ────────────────────────────────────

    def _start_gopro_stream(self, mode: str) -> None:
        """Send HTTP request to GoPro to start streaming."""
        if mode == "viewfinder":
            url = f"http://{self._gopro_ip}:8080/gopro/camera/stream/start"
        else:
            url = f"http://{self._gopro_ip}:8080/gopro/webcam/start"
        try:
            resp = urlopen(url, timeout=5)
            logger.debug("GoPro stream start (%s): %s", mode, resp.read())
        except Exception as e:
            logger.warning("GoPro stream start failed (%s): %s", mode, e)

    def _stop_gopro_stream(self) -> None:
        """Send HTTP request to GoPro to stop streaming."""
        try:
            urlopen(f"http://{self._gopro_ip}:8080/gopro/webcam/stop", timeout=5)
        except Exception:
            pass

    # ── keep-alive & health ────────────────────────────────────

    async def _keep_alive_loop(self) -> None:
        """Re-issue stream start every 60s to prevent GoPro timeout."""
        while self._running:
            await asyncio.sleep(60)
            if self._running and self._mode:
                logger.debug("Keep-alive: refreshing %s stream", self._mode)
                self._start_gopro_stream(self._mode)

    async def _health_monitor(self) -> None:
        """Monitor UDP data flow. Restart stream if silent for >30s."""
        await asyncio.sleep(30)  # Initial grace period for stream setup
        while self._running:
            silence = time.monotonic() - self._last_data_time
            if silence > 30:
                logger.warning("Stream silent for %.0fs, restarting...", silence)
                if self._mode:
                    self._start_gopro_stream(self._mode)
                self._last_data_time = time.monotonic()
            await asyncio.sleep(10)

    # ── PCR latency estimation ──────────────────────────────────

    def _sample_pcr(self, data: bytes) -> None:
        """Parse MPEG-TS PCR from a UDP datagram, update latency estimate.

        Validates PCR values to reject false positives from random byte
        sequences that happen to match the TS sync + PCR flag pattern.
        """
        pcr_ticks = self._extract_pcr(data)
        if pcr_ticks is None:
            return
        pi_now = time.monotonic()
        pcr_s = pcr_ticks / 27_000_000.0

        # First valid PCR — seed the baseline
        if self._pcr_first_pi is None:
            self._pcr_first_pi = pi_now
            self._pcr_first_val = pcr_s
            self._pcr_last_pi = pi_now
            self._pcr_last_val = pcr_s
            return

        # Discard duplicates and non-monotonic values (garbage detections)
        if pcr_s <= self._pcr_last_val:
            return

        # PCR clock must run at ~real-time rate (27 MHz ± 10%).
        # Random TS-packet-like byte sequences in the payload will have
        # PCR values that drift wildly — this filter rejects them.
        pcr_dt = pcr_s - self._pcr_last_val
        pi_dt = pi_now - self._pcr_last_pi
        if pi_dt > 0.001:
            rate = pcr_dt / pi_dt
            if rate < 0.9 or rate > 1.1:
                logger.debug("PCR rate anomaly: %.2f (expected ~1.0), discarding", rate)
                return

        self._pcr_last_pi = pi_now
        self._pcr_last_val = pcr_s

        # Latency delta from baseline (ms).
        # Positive = Pi time pulling ahead of PCR → buffering growing.
        pi_delta = pi_now - self._pcr_first_pi
        pcr_delta = pcr_s - self._pcr_first_val
        self._pcr_latency_ms = (pi_delta - pcr_delta) * 1000.0

    @staticmethod
    def _extract_pcr(data: bytes) -> int | None:
        """Extract PCR value from a UDP datagram containing MPEG-TS packets.

        Each TS packet is 188 bytes. Scans for sync byte (0x47), then
        reads the adaptation field for a PCR timestamp.
        Returns PCR ticks (27 MHz) or None if no PCR found.
        """
        if len(data) < 188:
            return None
        for offset in range(0, len(data) - 187, 188):
            if data[offset] != 0x47:
                continue
            # Adaptation field control is bits 4-5 of byte 3
            afc = (data[offset + 3] >> 4) & 0x3
            if afc < 2:
                continue  # No adaptation field
            af_len = data[offset + 4]
            if af_len == 0 or offset + 11 >= len(data):
                continue
            if not (data[offset + 5] & 0x10):  # PCR flag
                continue
            # PCR: 33-bit base + 6-bit reserved + 9-bit extension
            b = offset
            pcr_base = (
                (data[b + 6] << 25) | (data[b + 7] << 17) |
                (data[b + 8] << 9)  | (data[b + 9] << 1) |
                (data[b + 10] >> 7)
            )
            pcr_ext = ((data[b + 10] & 0x01) << 8) | data[b + 11]
            return pcr_base * 300 + pcr_ext
        return None

    # ── UDP receiver ──────────────────────────────────────────

    async def _start_udp_receiver(self, relay) -> None:
        """Create a UDP listener that feeds data to the relay."""
        loop = asyncio.get_event_loop()
        self._reader = asyncio.StreamReader()
        manager = self

        class _UDPFeeder(asyncio.DatagramProtocol):
            def __init__(self, reader):
                self._reader = reader

            def connection_made(self, transport):
                pass

            def datagram_received(self, data, addr):
                self._reader.feed_data(data)
                manager._last_data_time = time.monotonic()
                manager._sample_pcr(data)
                # Forward directly to Host via UDP (low-latency path)
                if manager._forward_addr is not None:
                    try:
                        transport.sendto(data, manager._forward_addr)
                    except OSError:
                        pass  # Host unreachable, drop silently

            def connection_lost(self, exc):
                if exc:
                    logger.debug("UDP receive error: %s", exc)
                self._reader.feed_eof()

            def error_received(self, exc):
                logger.debug("UDP error: %s", exc)

        transport, _protocol = await loop.create_datagram_endpoint(
            lambda: _UDPFeeder(self._reader),
            local_addr=("0.0.0.0", UDP_PORT),
            reuse_port=True,
        )
        self._transport = transport
        self._running = True
        self._last_data_time = time.monotonic()
        # Reset PCR latency tracking for new stream
        self._pcr_first_pi = None
        self._pcr_first_val = None
        self._pcr_last_pi = 0.0
        self._pcr_last_val = 0.0
        self._pcr_latency_ms = 0.0
        await relay.start(self._reader)

        # Keep-alive: prevent GoPro stream timeout every 60s.
        # Health monitoring is handled by the outer reconnection loop in main.py.
        self._keep_alive_task = asyncio.create_task(self._keep_alive_loop())

    async def _stop_internal(self) -> None:
        """Stop UDP receiver and GoPro stream."""
        self._running = False
        self._mode = None
        for task in [self._keep_alive_task, self._health_task]:
            if task:
                task.cancel()
        self._keep_alive_task = None
        self._health_task = None
        if self._transport:
            self._transport.close()
            self._transport = None
            await asyncio.sleep(0.2)  # Let OS release the UDP port
        if self._reader is not None:
            self._reader.feed_eof()
            self._reader = None
        self._stop_gopro_stream()
