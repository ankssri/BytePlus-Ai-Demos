"""Tiny circuit breaker + bounded-retry helper."""
import time, random

_STATE: dict[str, dict] = {}  # key -> {failures, open_until}

def _s(key: str) -> dict:
    return _STATE.setdefault(key, {"failures": 0, "open_until": 0.0})

def is_open(key: str) -> bool:
    return _s(key)["open_until"] > time.time()

def record_success(key: str):
    _STATE[key] = {"failures": 0, "open_until": 0.0}

def record_failure(key: str, threshold: int = 3, cooldown: float = 30.0):
    s = _s(key)
    s["failures"] += 1
    if s["failures"] >= threshold:
        s["open_until"] = time.time() + cooldown

def call_with_retry(fn, key: str, max_tries: int = 3, base_delay: float = 0.3):
    """Try fn up to max_tries times, respecting a per-key circuit breaker.

    fn() should return a dict with 'ok': bool. Raises RuntimeError if the
    breaker is open.
    """
    if is_open(key):
        return {"ok": False, "error": f"circuit_open:{key}"}
    last = None
    for attempt in range(1, max_tries + 1):
        try:
            res = fn()
        except Exception as e:  # noqa: BLE001
            res = {"ok": False, "error": f"exception:{e}"}
        last = res
        if res.get("ok"):
            record_success(key)
            res["_attempts"] = attempt
            return res
        # Only retry on likely-transient failures. Do not retry on
        # validation-style errors (e.g. "not found").
        err = str(res.get("error", ""))
        if any(x in err for x in ("not found", "invalid", "unknown")):
            break
        time.sleep(base_delay * (2 ** (attempt - 1)) + random.random() * 0.05)
    record_failure(key)
    last["_attempts"] = max_tries
    return last
