# VoltMart E-commerce Support Agent (demo)

A multi-agent customer-support demo that handles both simple FAQs
(return policy, refund timing, order status) and end-to-end
return + refund workflows with human gating, idempotent writes, and a
full audit trail — built to the design considerations in the task brief.

## Run

```bash
cd EcommerceSupportAgent
bash run.sh        # installs deps, starts FastAPI on :8000
```

Open:
- Chat UI:        http://localhost:8000/
- Audit dashboard http://localhost:8000/dashboard

The demo runs offline out of the box (rule-based classifier + templated
answers). To use BytePlus ModelArk for the LLM parts, export:

```bash
export ARK_API_KEY=<your key>
export ARK_MODEL=ep-2025xxxxxxxxxx           # your Ark endpoint id
# optional: ARK_BASE_URL=https://ark.ap-southeast.bytepluses.com/api/v3
```

## What to try

| Prompt                                    | What happens                                                    |
|-------------------------------------------|-----------------------------------------------------------------|
| "What is your return policy?"             | FAQ cache hit — no LLM, no downstream call.                     |
| "Where is my order O5003?"                | Read-only order+shipping MCP lookup.                            |
| "I want to return order O5001"            | Delivered $149, gold customer → auto-approved refund pipeline.  |
| "I want to return order O5007"            | Delivered $329 for an unverified standard customer → policy match but **human approval required**. Click "Approve refund" in the UI to complete. |
| "I want to return order O5005"            | Delivered $199, gold verified → auto-approved.                  |
| "Return order O5004"                      | Final-sale item — policy denies.                                |
| "Return order O5003"                      | Not delivered yet — policy denies.                              |
| "I want to speak to a human"              | Handoff intent — no downstream calls.                           |

## Architecture

```
                       ┌────────────────────┐
   user ── chat ─▶     │   Orchestrator     │  intent + safety scan
                       └─┬──────────────────┘
              routes to  │
         ┌───────────────┼─────────────────────┐
         ▼               ▼                     ▼
     FAQ agent      Order-status agent    Return/Refund agent
    (reversible)      (reversible)         (irreversible;
                                            human-gated writes;
                                            idempotency keys)
         │               │                     │
         └────────┬──────┴──────────┬──────────┘
                  ▼                 ▼
         ┌──────────────┐   ┌──────────────────┐
         │ FAQ cache    │   │  MCP servers     │  user | product | order
         │ (static)     │   │  (in-process)    │  payment | shipping | policy
         └──────────────┘   └──────────────────┘
                                  │
                        ┌─────────┴─────────┐
                        ▼                   ▼
                   Circuit breaker      Audit log (SQLite)
                   + bounded retry     — every step, every I/O
```

### Design considerations, mapped

| Requirement                                              | Implementation                                                       |
|----------------------------------------------------------|-----------------------------------------------------------------------|
| 1. Orchestrator intent → sub-agents                      | `agents/orchestrator.py` (rule + LLM classify, `INTENT_TABLE`)        |
| 2. Reversible vs. irreversible + human gate              | `INTENT_TABLE` tags category; policy MCP decides `auto_approve`; write agents pause and expose `proposed_action` for `/api/human/approve`. |
| 3. Auditable, resumable steps                            | `core/audit.py` (SQLite `cases`+`steps`), `resume_state()` returns last completed step. |
| 4. Idempotent writes                                     | `core/idempotency.py` — key derived from case+op+params; `refund_payment`, `update_order_status`, `create_return_label` all wrapped. |
| 5. Tool-call limits + no infinite loops                  | `circuit_breaker.call_with_retry` (max 3 tries, exp backoff, per-tool breaker) + `MAX_STEPS_PER_CASE` in `agents/base.py`. |
| 7. Separate systems per domain                           | 6 MCP-shaped modules under `mcp_servers/`, each with its own store.   |
| 8. Access via MCP, not direct API                        | Agents only call `self.tool(server, tool, params)`; the same contract could swap to real MCP transports. |
| 9. Mocked electronics store data                         | `mock_data/{users,products,orders,payments,shipping}.json`, `policies.md`. |
| 10. Prompt-injection guard, FAQ cache, step ceiling, circuit breaker, human fallback | `core/safety.py`, `core/cache.py`, `MAX_STEPS_PER_CASE`, `circuit_breaker.py`, `awaiting_human` path. |
| 11. Dashboard for audit + success rate                   | `/dashboard` + `/api/stats`, `/api/cases`, `/api/case/{id}`.          |

## Layout

```
EcommerceSupportAgent/
├── app.py                   # FastAPI: /api/chat, /api/human/approve, /api/stats, /dashboard
├── agents/
│   ├── orchestrator.py
│   ├── faq_agent.py
│   ├── order_status_agent.py
│   ├── return_refund_agent.py
│   └── base.py              # bounded tool() with audit + circuit breaker
├── core/
│   ├── audit.py             # SQLite audit + resume
│   ├── idempotency.py       # run_once() keyed store
│   ├── circuit_breaker.py   # retries + open/close breaker
│   ├── cache.py             # FAQ cache
│   ├── safety.py            # prompt-injection & PII guard
│   └── llm.py               # BytePlus Ark client + offline fallback
├── mcp_servers/             # user | product | order | payment | shipping | policy
├── mock_data/               # JSON stores + policies.md
└── static/                  # chat UI + audit dashboard
```

## Notes / limits

- MCP servers here run in-process for a single-command demo. The same
  `call(server, tool, params)` contract is what an MCP client sees over
  stdio/HTTP, so swapping to real servers is a transport change.
- The audit sqlite (`audit.db`) is created on first run in the project
  root. Delete it to reset stats.
- `mock_data/*.json` is intentionally writable so the demo can show real
  state changes (`status: delivered → return_requested → refunded`, and
  `payments.refunded` accumulating). Restore from `git` to reset.
