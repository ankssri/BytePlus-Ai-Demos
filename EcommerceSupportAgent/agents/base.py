"""Shared helpers for all sub-agents: bounded MCP call with audit + circuit breaker."""
from __future__ import annotations
from mcp_servers import call as mcp_call
from core import audit, circuit_breaker

MAX_STEPS_PER_CASE = 12  # global ceiling on tool calls per case


class StepCeilingExceeded(Exception):
    pass


class Agent:
    name = "base"

    def __init__(self, case_id: str):
        self.case_id = case_id
        self._steps = 0

    def _tick(self):
        self._steps += 1
        if self._steps > MAX_STEPS_PER_CASE:
            raise StepCeilingExceeded(f"agent {self.name} exceeded {MAX_STEPS_PER_CASE} steps")

    def tool(self, server: str, tool: str, params: dict, *, side_effect: str | None = None,
             idempotency_key: str | None = None) -> dict:
        """Call an MCP tool with retry + breaker, and append to the audit log."""
        self._tick()
        key = f"{server}.{tool}"
        result = circuit_breaker.call_with_retry(
            lambda: mcp_call(server, tool, params), key=key, max_tries=3
        )
        se = side_effect or ("write" if tool in ("refund_payment", "update_order_status",
                                                  "create_return_label") else "read")
        audit.log_step(self.case_id, self.name, f"{server}.{tool}", se,
                       params, result, bool(result.get("ok")), idempotency_key)
        return result

    def decision(self, action: str, inp, outp, ok: bool = True):
        audit.log_step(self.case_id, self.name, action, "decision", inp, outp, ok)
