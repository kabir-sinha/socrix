"""Append-only, hash-chained audit log (B12). Each entry commits to the previous entry's hash,
so any edit or deletion breaks the chain and is detectable by verify()."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from . import config as C


def _last_hash() -> str:
    if not C.AUDIT_LOG.exists():
        return "GENESIS"
    last = None
    with open(C.AUDIT_LOG) as f:
        for line in f:
            if line.strip():
                last = line
    return json.loads(last)["hash"] if last else "GENESIS"


def audit(event: str, detail: dict | None = None, actor: str = "system") -> dict:
    C.AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "actor": actor, "event": event,
             "detail": detail or {}, "engine": C.ENGINE_VERSION, "catalogue": C.CATALOGUE_VERSION, "prev": _last_hash()}
    entry["hash"] = hashlib.sha256(json.dumps(entry, sort_keys=True, default=str).encode()).hexdigest()
    with open(C.AUDIT_LOG, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")
    return entry


def verify() -> tuple[bool, int]:
    """Recompute the chain. Returns (intact, number_of_entries)."""
    if not C.AUDIT_LOG.exists():
        return True, 0
    prev, n = "GENESIS", 0
    with open(C.AUDIT_LOG) as f:
        for line in f:
            if not line.strip():
                continue
            e = json.loads(line); n += 1
            h = e.pop("hash")
            if e["prev"] != prev or hashlib.sha256(json.dumps(e, sort_keys=True, default=str).encode()).hexdigest() != h:
                return False, n
            prev = h
    return True, n
