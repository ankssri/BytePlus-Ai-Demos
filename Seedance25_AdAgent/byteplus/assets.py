"""BytePlus Asset Library (HMAC-SHA256 AK/SK). Register reference assets so
Seedance 2.5 can use them as omni references (`asset://<id>`)."""

import hashlib
import hmac
import json
from datetime import datetime, timezone

import requests

from . import config as C


def _sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signed_headers(action, body_str):
    body_hash = hashlib.sha256(body_str.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    date_str, dt_str = now.strftime("%Y%m%d"), now.strftime("%Y%m%dT%H%M%SZ")
    canonical_headers = (f"content-type:application/json\nhost:{C.ASSET_HOST}\n"
                         f"x-content-sha256:{body_hash}\nx-date:{dt_str}\n")
    signed = "content-type;host;x-content-sha256;x-date"
    query = f"Action={action}&Version={C.ASSET_VERSION}"
    canonical_request = "\n".join(["POST", "/", query, canonical_headers, signed, body_hash])
    scope = f"{date_str}/{C.ASSET_REGION}/{C.ASSET_SERVICE}/request"
    string_to_sign = "\n".join(["HMAC-SHA256", dt_str, scope,
                                hashlib.sha256(canonical_request.encode()).hexdigest()])
    k = _sign(_sign(_sign(_sign(C.ark_sk().encode(), date_str), C.ASSET_REGION),
                    C.ASSET_SERVICE), "request")
    sig = hmac.new(k, string_to_sign.encode(), hashlib.sha256).hexdigest()
    auth = f"HMAC-SHA256 Credential={C.ark_ak()}/{scope}, SignedHeaders={signed}, Signature={sig}"
    return {"Content-Type": "application/json", "Host": C.ASSET_HOST, "X-Date": dt_str,
            "X-Content-Sha256": body_hash, "Authorization": auth}


def call(action, body):
    if not C.ark_ak() or not C.ark_sk():
        return {"error": "ARK_AK and ARK_SK are required for asset APIs"}, 500
    body_str = json.dumps(body, separators=(",", ":"))
    url = f"{C.ASSET_BASE}/?Action={action}&Version={C.ASSET_VERSION}"
    try:
        resp = requests.post(url, headers=_signed_headers(action, body_str),
                             data=body_str, timeout=30)
        print(f"[asset:{action}] status={resp.status_code}")
        return C.safe_json(resp), resp.status_code
    except Exception as e:
        return {"error": str(e)}, 500


def create(group_id, url, name, asset_type="Image"):
    body = {"GroupId": group_id, "URL": url, "AssetType": asset_type,
            "Name": name, "ProjectName": "default"}
    data, status = call("CreateAsset", body)
    if status not in (200, 201) or "error" in data:
        return {"error": data, "http_status": status}, max(status, 400)
    return {"id": (data.get("Result") or {}).get("Id"), "raw": data}, 200


def get(asset_id):
    data, status = call("GetAsset", {"Id": asset_id, "ProjectName": "default"})
    r = data.get("Result") or {}
    return {"id": asset_id, "status": r.get("Status", ""), "url": r.get("URL", ""), "raw": data}, status


def list_assets(group_id, page_size=50):
    body = {"Filter": {"GroupIds": [group_id], "GroupType": "AIGC"},
            "PageNumber": 1, "PageSize": page_size, "SortBy": "CreateTime",
            "SortOrder": "Desc", "ProjectName": "default"}
    data, status = call("ListAssets", body)
    if status not in (200, 201) or "error" in data:
        return {"error": data, "http_status": status}, max(status, 400)
    items = (data.get("Result") or {}).get("Items") or []
    return {"assets": [{"id": a.get("Id"), "name": a.get("Name"), "url": a.get("URL"),
                        "asset_type": a.get("AssetType"), "status": a.get("Status")}
                       for a in items]}, 200
