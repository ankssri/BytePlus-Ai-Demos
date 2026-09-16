"""FastAPI app: chat endpoint, human-approval endpoint, audit dashboard API, static UI."""
from __future__ import annotations
import os, sys
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(__file__))

from agents.orchestrator import Orchestrator
from agents.return_refund_agent import ReturnRefundAgent
from core import audit
from mcp_servers import list_all_tools

app = FastAPI(title="VoltMart Support Agent Demo")
orch = Orchestrator()


class ChatIn(BaseModel):
    message: str
    order_id: str | None = None
    user_id: str | None = None


class ApproveIn(BaseModel):
    case_id: str
    order_id: str
    approve: bool


@app.post("/api/chat")
def chat(inp: ChatIn):
    return orch.handle(inp.message, order_id=inp.order_id, user_id=inp.user_id)


@app.post("/api/human/approve")
def human_approve(inp: ApproveIn):
    """Human agent confirms (or denies) a pending return/refund case."""
    if not inp.approve:
        audit.log_step(inp.case_id, "human", "denied", "decision",
                       {"order_id": inp.order_id}, None, ok=True)
        audit.finish_case(inp.case_id, "done", "human denied refund")
        return {"case_id": inp.case_id, "reply": "Human agent denied the refund.",
                "requires_human": False}
    agent = ReturnRefundAgent(inp.case_id)
    out = agent.handle(f"approve return for {inp.order_id}",
                       inp.order_id, human_approved=True)
    audit.finish_case(inp.case_id, "done", "human approved; refund processed")
    return {"case_id": inp.case_id, **out}


@app.get("/api/cases")
def cases():
    return {"cases": audit.list_cases(100)}


@app.get("/api/case/{case_id}")
def case_detail(case_id: str):
    c = audit.get_case(case_id)
    return c or JSONResponse({"error": "not found"}, status_code=404)


@app.get("/api/case/{case_id}/resume")
def case_resume(case_id: str):
    return audit.resume_state(case_id)


@app.get("/api/stats")
def stats():
    return audit.stats()


@app.get("/api/tools")
def tools():
    return {"tools": list_all_tools()}


# ---- static UI ----------------------------------------------------------
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/dashboard")
def dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "dashboard.html"))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
