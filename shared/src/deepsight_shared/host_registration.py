"""Proof of possession for a Pi-issued, single-use registration challenge."""

import hashlib
import hmac
import os
from pathlib import Path

LEASE_SECONDS = 15
RENEW_SECONDS = 5


def pairing_key(key_file: Path | None = None) -> bytes | None:
    value = os.environ.get("DEEPSIGHT_HOST_PAIRING_KEY")
    if not value and key_file is not None:
        value = key_file.read_text(encoding="ascii").strip()
    if not value:
        if key_file is not None:
            raise ValueError("Host pairing key file is empty")
        return None
    key = bytes.fromhex(value)
    if len(key) != 32:
        raise ValueError("DEEPSIGHT_HOST_PAIRING_KEY must be a 32-byte hex key")
    return key


def registration_proof(key: bytes, nonce: str, address: str) -> str:
    return hmac.new(key, f"deepsight/host-register/v1:{nonce}:{address}".encode(),
                    hashlib.sha256).hexdigest()
