"""SQLite-backed audit log.

Every step of every case is recorded so the orchestrator can resume a
crashed case from the last completed step (see resume_case).
"""
from __future__ import annotations
import json, os, sqlite3, threading, time, uuid

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "audit.db")
_LOCK = threading.Lock()


def _conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _LOCK, _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS cases (
            case_id TEXT PRIMARY KEY,
            created REAL, updated REAL,
            user_query TEXT,
            intent TEXT,
            status TEXT,           -- running | done | failed | awaiting_human
            outcome TEXT           -- final message summary
        );
        CREATE TABLE IF NOT EXISTS steps (
            step_id TEXT PRIMARY KEY,
            case_id TEXT,
            ts REAL,
            agent TEXT,
            action TEXT,           -- tool call / decision / message
            side_effect TEXT,      -- 'read' | 'write' | 'decision'
            input_json TEXT,
            output_json TEXT,
            ok INTEGER,
            idempotency_key TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_steps_case ON steps(case_id, ts);
        CREATE TABLE IF NOT EXISTS idempotency (
            key TEXT PRIMARY KEY,
            case_id TEXT,
            result_json TEXT,
            ts REAL
        );
        """)


def start_case(user_query: str, intent: str = "unknown") -> str:
    case_id = "C-" + uuid.uuid4().hex[:10]
    now = time.time()
    with _LOCK, _conn() as c:
        c.execute(
            "INSERT INTO cases(case_id,created,updated,user_query,intent,status,outcome) VALUES (?,?,?,?,?,?,?)",
            (case_id, now, now, user_query, intent, "running", None),
        )
    return case_id


def set_intent(case_id: str, intent: str):
    with _LOCK, _conn() as c:
        c.execute("UPDATE cases SET intent=?, updated=? WHERE case_id=?", (intent, time.time(), case_id))


def finish_case(case_id: str, status: str, outcome: str):
    with _LOCK, _conn() as c:
        c.execute("UPDATE cases SET status=?, outcome=?, updated=? WHERE case_id=?",
                  (status, outcome, time.time(), case_id))


def log_step(case_id: str, agent: str, action: str, side_effect: str,
             input_data, output_data, ok: bool, idempotency_key: str | None = None) -> str:
    step_id = "S-" + uuid.uuid4().hex[:10]
    with _LOCK, _conn() as c:
        c.execute(
            "INSERT INTO steps VALUES (?,?,?,?,?,?,?,?,?,?)",
            (step_id, case_id, time.time(), agent, action, side_effect,
             json.dumps(input_data, default=str), json.dumps(output_data, default=str),
             1 if ok else 0, idempotency_key),
        )
        c.execute("UPDATE cases SET updated=? WHERE case_id=?", (time.time(), case_id))
    return step_id


def get_case(case_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if not row:
            return None
        case = dict(row)
        steps = [dict(r) for r in c.execute(
            "SELECT * FROM steps WHERE case_id=? ORDER BY ts", (case_id,)).fetchall()]
        for s in steps:
            s["input"] = json.loads(s.pop("input_json") or "null")
            s["output"] = json.loads(s.pop("output_json") or "null")
        case["steps"] = steps
        return case


def list_cases(limit: int = 50) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT case_id,created,intent,status,outcome FROM cases ORDER BY created DESC LIMIT ?",
            (limit,)).fetchall()
        return [dict(r) for r in rows]


def stats() -> dict:
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        by_status = {r[0]: r[1] for r in c.execute(
            "SELECT status,COUNT(*) FROM cases GROUP BY status").fetchall()}
        by_intent = {r[0]: r[1] for r in c.execute(
            "SELECT intent,COUNT(*) FROM cases GROUP BY intent").fetchall()}
        write_steps = c.execute("SELECT COUNT(*) FROM steps WHERE side_effect='write'").fetchone()[0]
        cache_hits = c.execute("SELECT COUNT(*) FROM steps WHERE action='faq_cache_hit'").fetchone()[0]
        human_handoffs = c.execute("SELECT COUNT(*) FROM cases WHERE status='awaiting_human'").fetchone()[0]
    done = by_status.get("done", 0)
    success_rate = (done / total * 100.0) if total else 0.0
    return {
        "total_cases": total, "by_status": by_status, "by_intent": by_intent,
        "write_actions": write_steps, "faq_cache_hits": cache_hits,
        "human_handoffs": human_handoffs, "success_rate_pct": round(success_rate, 1),
    }


def resume_state(case_id: str) -> dict:
    """Return the last completed step for a case so an agent can restart from it."""
    case = get_case(case_id)
    if not case:
        return {"resumable": False, "reason": "unknown case"}
    if case["status"] in ("done", "failed"):
        return {"resumable": False, "reason": f"case already {case['status']}"}
    completed = [s for s in case["steps"] if s["ok"]]
    return {"resumable": True, "case": case, "last_step": completed[-1] if completed else None}


init_db()
