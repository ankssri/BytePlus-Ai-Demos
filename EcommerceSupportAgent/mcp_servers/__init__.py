"""In-process MCP-style servers.

Each module exposes:
    NAME: str
    TOOLS: dict[str, dict]  # tool_name -> {description, params_schema, side_effect: 'read'|'write'}
    def call(tool: str, params: dict) -> dict

This mirrors the MCP tool contract (list_tools + call_tool) so the same
agent code could later target real MCP servers over stdio/HTTP by swapping
the transport.
"""
from . import user_mcp, product_mcp, order_mcp, payment_mcp, shipping_mcp, policy_mcp

REGISTRY = {
    m.NAME: m for m in (user_mcp, product_mcp, order_mcp, payment_mcp, shipping_mcp, policy_mcp)
}


def list_all_tools():
    out = []
    for name, mod in REGISTRY.items():
        for tool, spec in mod.TOOLS.items():
            out.append({"server": name, "tool": tool, **spec})
    return out


def call(server: str, tool: str, params: dict) -> dict:
    if server not in REGISTRY:
        return {"ok": False, "error": f"unknown MCP server '{server}'"}
    mod = REGISTRY[server]
    if tool not in mod.TOOLS:
        return {"ok": False, "error": f"unknown tool '{tool}' on '{server}'"}
    try:
        return mod.call(tool, params)
    except Exception as e:  # noqa: BLE001 - surface tool errors to agent
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
