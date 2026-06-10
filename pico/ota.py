"""OTA firmware update receiver for Pico.

Receives file chunks over USB CDC, writes to flash, verifies SHA256,
and performs atomic rename on commit.
"""

import gc
import hashlib
import os
import time

try:
    from ubinascii import a2b_base64
except ImportError:
    from binascii import a2b_base64

try:
    from machine import reset as machine_reset
except ImportError:
    def machine_reset():
        import sys
        sys.exit(0)

_OTA_DIR = "_ota"
_CHUNK_SIZE = 512
_TIMEOUT_S = 30


class OTAReceiver:
    def __init__(self, serial_write_fn):
        self._write = serial_write_fn
        self._active = False
        self._manifest = []
        self._last_activity = 0
        self._received = {}

    @property
    def active(self):
        return self._active

    def handle_begin(self, payload):
        files = payload.get("files", [])
        if not files:
            return {"step": "begin", "ok": False, "error": "no files"}

        self._cleanup()
        try:
            os.mkdir(_OTA_DIR)
        except OSError:
            pass

        self._manifest = files
        self._received = {f["name"]: 0 for f in files}
        self._active = True
        self._last_activity = time.time()
        gc.collect()
        return {"step": "begin", "ok": True, "files": len(files)}

    def handle_chunk(self, payload):
        if not self._active:
            return {"step": "chunk", "ok": False, "error": "no session"}

        self._last_activity = time.time()
        fname = payload.get("file", "")
        seq = payload.get("seq", -1)
        data_b64 = payload.get("data", "")
        is_last = payload.get("last", False)

        if fname not in self._received:
            return {"step": "chunk", "ok": False, "error": "unknown file"}

        try:
            raw = a2b_base64(data_b64)
        except Exception:
            return {"step": "chunk", "ok": False, "error": "decode"}

        path = _OTA_DIR + "/" + fname
        try:
            with open(path, "ab") as f:
                f.write(raw)
        except Exception as e:
            return {"step": "chunk", "ok": False, "error": str(e)}

        self._received[fname] += len(raw)
        gc.collect()
        return {"step": "chunk", "file": fname, "seq": seq, "ok": True}

    def handle_commit(self, payload):
        if not self._active:
            return {"step": "commit", "ok": False, "error": "no session"}

        errors = []
        for finfo in self._manifest:
            fname = finfo["name"]
            expected_size = finfo.get("size", -1)
            expected_sha = finfo.get("sha256", "")
            path = _OTA_DIR + "/" + fname

            actual_size = self._received.get(fname, 0)
            if expected_size >= 0 and actual_size != expected_size:
                errors.append("%s: size %d != %d" % (fname, actual_size, expected_size))
                continue

            if expected_sha:
                h = hashlib.sha256()
                try:
                    with open(path, "rb") as f:
                        while True:
                            chunk = f.read(256)
                            if not chunk:
                                break
                            h.update(chunk)
                except Exception as e:
                    errors.append("%s: read error %s" % (fname, e))
                    continue
                actual_sha = "".join("%02x" % b for b in h.digest())
                if actual_sha != expected_sha:
                    errors.append("%s: sha256 mismatch" % fname)

        if errors:
            self._abort()
            return {"step": "commit", "ok": False, "errors": errors}

        for finfo in self._manifest:
            fname = finfo["name"]
            src = _OTA_DIR + "/" + fname
            dst = fname
            try:
                os.remove(dst)
            except OSError:
                pass
            os.rename(src, dst)

        self._cleanup()
        self._active = False
        return {"step": "commit", "ok": True, "reset": True}

    def post_commit_reset(self):
        """Call after ACK is sent to perform the actual reset."""
        time.sleep(0.1)
        machine_reset()

    def check_timeout(self):
        if not self._active:
            return
        if time.time() - self._last_activity > _TIMEOUT_S:
            self._abort()

    def _abort(self):
        self._cleanup()
        self._active = False
        self._manifest = []
        self._received = {}

    def _cleanup(self):
        try:
            entries = os.listdir(_OTA_DIR)
            for e in entries:
                os.remove(_OTA_DIR + "/" + e)
            os.rmdir(_OTA_DIR)
        except OSError:
            pass
        gc.collect()
