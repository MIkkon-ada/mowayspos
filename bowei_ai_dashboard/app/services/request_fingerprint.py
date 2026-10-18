"""Canonical fingerprints for retry-safe write requests."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def request_payload_fingerprint(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
