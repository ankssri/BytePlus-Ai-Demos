import json, os, threading

_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mock_data")
_LOCKS: dict[str, threading.Lock] = {}

def _lock(name: str) -> threading.Lock:
    if name not in _LOCKS:
        _LOCKS[name] = threading.Lock()
    return _LOCKS[name]

def load(name: str) -> dict:
    with open(os.path.join(_BASE, f"{name}.json"), "r") as f:
        return json.load(f)

def save(name: str, data: dict) -> None:
    with _lock(name):
        path = os.path.join(_BASE, f"{name}.json")
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)

def load_text(fname: str) -> str:
    with open(os.path.join(_BASE, fname), "r") as f:
        return f.read()
