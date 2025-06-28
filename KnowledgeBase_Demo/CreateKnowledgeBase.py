import json
import os
import requests
from dotenv import load_dotenv
from volcengine.auth.SignerV4 import SignerV4
from volcengine.base.Request import Request
from volcengine.Credentials import Credentials

# Load environment variables
load_dotenv()

# Signature generation logic. 
def prepare_request(method, path, params=None, data=None, doseq=0): 
    # Create a request. 
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
    # Generate a signature. 
    credentials = Credentials(ak, sk, "air", "cn-north-1") 
    SignerV4.sign(r, credentials) 
    return r 

# Knowledge base creation logic. 
def create(): 
    # Request method for creating a knowledge base. 
    method = "POST" 
    # Request path for creating a knowledge base. 
    path = "/api/knowledge/collection/create" 
    # Parameters required for creating a knowledge base. 
    request_params = { 
        "name": "ankurDemoKB", 
        "data_type": "unstructured_data", 
        "preprocessing": { 
            "chunking_strategy":"custom_balance", 
            "multi_modal":["image_ocr"] 
        }, 
        "index": { 
            "cpu_quota": 1, 
            "embedding_model": "bge-large-zh-and-m3", 
            "embedding_dimension": 2048, 
            "quant": "int8", 
            "index_type": "hnsw_hybrid" 
        }, 
    } 
    info_req = prepare_request(method=method, path=path, data=request_params)
    rsp = requests.request(
        method=info_req.method,
        url="https://{}{}".format(g_knowledge_base_domain, info_req.path),
        headers=info_req.headers,
        data=info_req.body
    )
    print(rsp.text)

if __name__ == "__main__": 
    ak = os.getenv('AK')
    sk = os.getenv('SK')
    g_knowledge_base_domain = os.getenv('KNOWLEDGE_BASE_DOMAIN')
    account_id = os.getenv('ACCOUNT_ID')
    # Call the function to create a knowledge base
    create()