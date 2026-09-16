from . import _util

NAME = "user"
TOOLS = {
    "get_user": {
        "description": "Fetch a user profile by user_id.",
        "params": {"user_id": "str"},
        "side_effect": "read",
    },
    "find_user_by_email": {
        "description": "Look up a user by email address.",
        "params": {"email": "str"},
        "side_effect": "read",
    },
}

def call(tool, params):
    users = _util.load("users")
    if tool == "get_user":
        u = users.get(params.get("user_id", ""))
        return {"ok": bool(u), "user": u} if u else {"ok": False, "error": "user not found"}
    if tool == "find_user_by_email":
        email = (params.get("email") or "").lower()
        for u in users.values():
            if u["email"].lower() == email:
                return {"ok": True, "user": u}
        return {"ok": False, "error": "user not found"}
    return {"ok": False, "error": "unknown tool"}
