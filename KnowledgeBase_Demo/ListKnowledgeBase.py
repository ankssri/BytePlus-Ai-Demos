import json
import os
import requests
from dotenv import load_dotenv
from volcengine.auth.SignerV4 import SignerV4
from volcengine.base.Request import Request
from volcengine.Credentials import Credentials

# Load environment variables
load_dotenv()

# Signature generation logic
def prepare_request(method, path, params=None, data=None, doseq=0):
    # Create a request
    if params:
        for key in params:
            if (
                    isinstance(params[key], int)
                    or isinstance(params[key], float)
                    or isinstance(params[key], bool)
            ):
                params[key] = str(params[key])
            elif isinstance(params[key], list):
                if not doseq:
                    params[key] = ",".join(params[key])
    r = Request()
    r.set_shema("http")
    r.set_method(method)
    r.set_connection_timeout(10)
    r.set_socket_timeout(10)
    mheaders = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Host": g_knowledge_base_domain,
        "V-Account-Id": account_id,
    }
    r.set_headers(mheaders)
    if params:
        r.set_query(params)
    r.set_host(g_knowledge_base_domain)
    r.set_path(path)
    if data is not None:
        r.set_body(json.dumps(data))
    # Generate a signature
    credentials = Credentials(ak, sk, "air", "cn-north-1")
    SignerV4.sign(r, credentials)
    return r

# Knowledge base listing logic
def list_knowledge_bases():
    # Request method for listing knowledge bases
    method = "POST"
    # Request path for listing knowledge bases
    path = "/api/knowledge/collection/list"
    # Parameters required for listing knowledge bases
    request_params = {
        "project": "Default",
        "brief": False
    }
    info_req = prepare_request(method=method, path=path, data=request_params)
    # Remove redundant request implementation
    rsp = requests.request(
        method=info_req.method,
        url="https://{}{}".format(g_knowledge_base_domain, info_req.path),
        headers=info_req.headers,
        data=info_req.body,
        timeout=30
    )

    try:
        rsp.raise_for_status()
        response_data = rsp.json()
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {str(e)}")
        return
    except json.JSONDecodeError:
        print("Failed to parse response JSON")
        return

    if rsp.status_code == 200 and response_data.get("code") == 0:
        collection_list = response_data["data"].get("collection_list", [])
        print(f"\nAvailable Knowledge Bases ({len(collection_list)}):")
        if not collection_list:
            print("No knowledge bases found")
        else:
            for kb in collection_list:
                print(f"- {kb['collection_name']} ({kb['description']})")
                print(f"  Data Type: {kb['data_type']}")
            print("-" * 30)
        print(f"Total Knowledge Bases: {response_data['data']['total_num']}")
    else:
        print(f"Error: {response_data['message']}")

if __name__ == "__main__":
    ak = os.getenv('AK')
    sk = os.getenv('SK')
    g_knowledge_base_domain = os.getenv('KNOWLEDGE_BASE_DOMAIN')
    account_id = os.getenv('ACCOUNT_ID')
    # Call the function to list knowledge bases
    list_knowledge_bases()