"""Idempotency store — same key returns the cached result rather than re-executing.

Wraps the audit sqlite so restarts survive.
"""
import json, sqlite3, time, hashlib
from . import audit


def make_key(*parts) -> str:
    raw = "|".join(str(p) for p in parts)
    return "idem_" + hashlib.sha256(raw.encode()).hexdigest()[:20]


def get(key: str):
    with audit._conn() as c:
        row = c.execute("SELECT result_json FROM idempotency WHERE key=?", (key,)).fetchone()
        return json.loads(row["result_json"]) if row else None


def put(key: str, case_id: str, result: dict):
    with audit._LOCK, audit._conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO idempotency(key,case_id,result_json,ts) VALUES (?,?,?,?)",
            (key, case_id, json.dumps(result, default=str), time.time()),
        )


def run_once(key: str, case_id: str, fn):
    """Execute fn() at most once per key. Second call returns the cached dict."""
    hit = get(key)
    if hit is not None:
        return {"idempotent_replay": True, **hit}
    result = fn()
    put(key, case_id, result)
    return result
