from . import _util

NAME = "product"
TOOLS = {
    "get_product": {"description": "Fetch product by id.", "params": {"product_id": "str"}, "side_effect": "read"},
}

def call(tool, params):
    products = _util.load("products")
    if tool == "get_product":
        p = products.get(params.get("product_id", ""))
        return {"ok": bool(p), "product": p} if p else {"ok": False, "error": "product not found"}
    return {"ok": False, "error": "unknown tool"}
