"""Bounded GoPro-only recovery worker; never resets the upstream hub."""
from __future__ import annotations
import asyncio
import json
import logging
import os
from pathlib import Path
import sys
import time
import urllib.request

log = logging.getLogger('gopro.recovery')


def camera_device(root=Path('/sys/bus/usb/devices')):
    for path in root.iterdir():
        try:
            if (path / 'idVendor').read_text().strip() == '2672' and (path / 'idProduct').read_text().strip() == '005a':
                return path
        except OSError:
            continue
    return None


class Recovery:
    def __init__(self, ip, state_file, cooldown_s=0, max_resets=None, error_threshold=8):
        self.cooldown_s = cooldown_s
        self.max_resets = max_resets
        self.error_threshold = error_threshold
        self.error_base = None
        self.error_identity = None
        self.action_lock = asyncio.Lock()
        self.ip = ip
        self.state_file = Path(state_file)
        self.failures = 0
        self.last_action = -float('inf')
        self.resets = []
        self.child = None
        self.network_tried = False
        try:
            self.resets = json.loads(self.state_file.read_text())
        except (OSError, ValueError):
            pass

    def probe(self):
        # A fresh connection avoids reusing GoPro's expired HTTP sessions.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        request = urllib.request.Request(f'http://{self.ip}:8080/gopro/camera/state', headers={'Connection': 'close'})
        try:
            with opener.open(request, timeout=2) as response:
                return isinstance(json.load(response).get('status'), dict)
        except Exception:
            return False

    async def command(self, *args, timeout=8):
        if self.child is not None and self.child.returncode is None:
            log.error('Previous recovery command is still blocked; no further reset issued')
            return False
        self.child = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        try:
            return await asyncio.wait_for(self.child.wait(), timeout) == 0
        except asyncio.TimeoutError:
            self.child.kill()
            log.error('Recovery command timed out: %s', args[0])
            return False

    async def step(self, healthy, now=None, wall=None, error_trigger=False):
        now = time.monotonic() if now is None else now
        wall = time.time() if wall is None else wall
        if healthy and not error_trigger:
            if self.failures:
                log.info('Camera HTTP recovered after %d failed checks', self.failures)
            self.failures = 0
            self.network_tried = False
            return
        self.failures += 1
        if self.failures == 1 and not error_trigger:
            log.warning('Camera not responding; waiting for repeated failures')
        if (not error_trigger and self.failures < 3) or now - self.last_action < self.cooldown_s:
            return
        if self.child is not None and self.child.returncode is None:
            if self.failures % 12 == 3:
                log.error('Recovery worker still blocked; waiting, no further reset issued')
            return
        device = camera_device()
        if device is None:
            if self.failures % 12 == 3:
                log.warning('Camera USB absent; waiting for re-enumeration, hub unchanged')
            return
        if not error_trigger and not self.network_tried:
            interfaces = list(device.glob('*/net/*'))
            if interfaces:
                self.last_action = now
                self.network_tried = True
                interface = interfaces[0].name
                address = os.environ.get('GOPRO_USB_ADDRESS', '172.22.121.50/24')
                configured = await self.command('/usr/sbin/ip', 'addr', 'replace',
                                                address, 'dev', interface)
                if configured:
                    configured = await self.command('/usr/sbin/ip', 'link', 'set',
                                                    'dev', interface, 'up')
                if configured and await asyncio.to_thread(self.probe):
                    restarted = await self.command('/usr/bin/systemctl', 'restart',
                                                   'deepsight-gopro-gateway.service')
                    log.info('Camera USB network restored on %s; gateway restart=%s',
                             interface, restarted)
                else:
                    log.warning('Camera USB network repair on %s did not restore HTTP',
                                interface)
                return
        self.resets = [stamp for stamp in self.resets if wall - stamp < 3600]
        if self.max_resets is not None and len(self.resets) >= self.max_resets:
            self.last_action = now
            log.error('USB reset limit reached (%d/hour); manual inspection required', self.max_resets)
            return
        bus = int((device / 'busnum').read_text())
        number = int((device / 'devnum').read_text())
        node = f'/dev/bus/usb/{bus:03d}/{number:03d}'
        # Persist before issuing the reset, including failures/timeouts.
        self.resets.append(wall)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.resets))
        self.last_action = now
        log.warning('Resetting GoPro USB device %s ONLY (attempt %d/%s this hour, error_trigger=%s)', node, len(self.resets), self.max_resets if self.max_resets is not None else 'unlimited', error_trigger)
        code = 'import os,fcntl,sys; fd=os.open(sys.argv[1],os.O_WRONLY); fcntl.ioctl(fd,0x5514,0); os.close(fd)'
        ok = await self.command(sys.executable, '-c', code, node)
        self.error_base = None
        self.network_tried = False
        log.warning('GoPro USB reset returned %s; HTTP checks will verify recovery', ok)

    async def check_errors(self):
        device = camera_device()
        if device is None:
            self.error_base = self.error_identity = None
            return
        interfaces = list(device.glob('*/net/*'))
        if not interfaces:
            return
        interface = interfaces[0]
        try:
            identity = (str(device.resolve()), (interface / 'ifindex').read_text().strip())
            counters = tuple(int((interface / 'statistics' / name).read_text())
                             for name in ('rx_errors', 'tx_errors'))
        except (OSError, ValueError):
            return
        if (self.error_identity != identity or self.error_base is None
                or any(value < base for value, base in zip(counters, self.error_base))):
            self.error_identity = identity
            self.error_base = counters
            return
        delta = sum(value - base for value, base in zip(counters, self.error_base))
        if delta >= self.error_threshold:
            async with self.action_lock:
                if time.monotonic() - self.last_action >= self.cooldown_s:
                    log.warning('Camera USB network error growth=%d (threshold=%d); direct device reset requested', delta, self.error_threshold)
                    await self.step(False, error_trigger=True)

    async def _http_loop(self):
        while True:
            try:
                healthy = await asyncio.to_thread(self.probe)
                async with self.action_lock:
                    await self.step(healthy)
            except Exception:
                log.exception('HTTP recovery check failed')
            await asyncio.sleep(5)

    async def _error_loop(self):
        while True:
            try:
                await self.check_errors()
            except Exception:
                log.exception('USB error check failed')
            await asyncio.sleep(1)

    async def run(self):
        log.info('Camera %s: USB errors every 1s, threshold=%d new RX+TX errors; HTTP every 5s; cooldown=%.0fs; max resets=%s/hour',
                 self.ip, self.error_threshold, self.cooldown_s, self.max_resets if self.max_resets is not None else "unlimited")
        await asyncio.gather(self._http_loop(), self._error_loop())


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    asyncio.run(Recovery(os.environ.get('GOPRO_IP', '172.22.121.51'),
                         '/var/lib/deepsight-gopro-recovery/resets.json').run())
