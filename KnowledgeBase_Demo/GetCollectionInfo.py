import json
import os
import requests
from dotenv import load_dotenv
from volcengine.auth.SignerV4 import SignerV4
from volcengine.base.Request import Request
from volcengine.Credentials import Credentials
import datetime

# Load environment variables
load_dotenv()

# Signature generation logic (reused from ListKnowledgeBase.py)
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
    r.set_shema("https") # Assuming http, change to https if your endpoint uses it
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
    credentials = Credentials(ak, sk, "air", "cn-north-1") # Ensure region is correct
    SignerV4.sign(r, credentials)
    return r

# Knowledge base collection info logic
def get_collection_info(collection_name, project_name=""):
    method = "POST"
    path = "/api/knowledge/collection/info"
    request_data = {
        "name": collection_name,
        "project": project_name
    }

    info_req = prepare_request(method=method, path=path, data=request_data)
    
    # Construct the full URL, ensuring it starts with https:// or http://
    # The domain from .env might or might not include the scheme.
    # The curl example uses https.
    url_scheme = "https://"
    if g_knowledge_base_domain.startswith("http://") or g_knowledge_base_domain.startswith("https://"):
        full_url = f"{g_knowledge_base_domain}{info_req.path}"
    else:
        full_url = f"{url_scheme}{g_knowledge_base_domain}{info_req.path}"

    rsp = None  # Initialize rsp to None
    try:
        rsp = requests.request(
            method=info_req.method,
            url=full_url,
            headers=info_req.headers,
            data=info_req.body,
            timeout=30
        )
        rsp.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
        response_data = rsp.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error occurred: {e}")
        if rsp is not None:
            print(f"Response content: {rsp.text}")
        return
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {str(e)}")
        return
    except json.JSONDecodeError:
        print("Failed to parse response JSON")
        if rsp is not None:
            print(f"Response content: {rsp.text}")
        return

    if rsp.status_code == 200 and response_data.get("code") == 0:
        data = response_data.get("data", {})
        print(f"\nCollection Information for: {data.get('collection_name')}")
        print(f"  Description: {data.get('description')}")
        create_time_ts = data.get('create_time')
        update_time_ts = data.get('update_time')
        if create_time_ts:
            print(f"  Created At: {datetime.datetime.fromtimestamp(create_time_ts).strftime('%Y-%m-%d %H:%M:%S')}")
        if update_time_ts:
            print(f"  Updated At: {datetime.datetime.fromtimestamp(update_time_ts).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Creator: {data.get('creator')}")
        print(f"  Resource ID: {data.get('resource_id')}")
        print(f"  Project: {data.get('project')}")
        
        pipeline_list = data.get('pipeline_list', [])
        if pipeline_list:
            print("  Pipelines:")
            for i, pipeline in enumerate(pipeline_list):
                print(f"    Pipeline {i+1}:")
                print(f"      Type: {pipeline.get('pipeline_type')}")
                print(f"      Data Type: {pipeline.get('data_type')}")
                # Add more details from pipeline_stat, index_list etc. if needed
        else:
            print("  No pipelines found.")
        print("-" * 30)
    else:
        print(f"Error Code: {response_data.get('code')}")
        print(f"Error Message: {response_data.get('message')}")
        print(f"Request ID: {response_data.get('request_id')}")

if __name__ == "__main__":
    ak = os.getenv('AK')
    sk = os.getenv('SK')
    g_knowledge_base_domain = os.getenv('KNOWLEDGE_BASE_DOMAIN')
    account_id = os.getenv('ACCOUNT_ID')

    if not all([ak, sk, g_knowledge_base_domain, account_id]):
        print("Error: AK, SK, KNOWLEDGE_BASE_DOMAIN, or ACCOUNT_ID environment variables are not set.")
        print("Please ensure your .env file is correctly configured and loaded.")
    else:
        # You'll need to provide the collection name you want to query.
        # For testing, you can use the one from the curl example or one you know exists.
        collection_to_query = "ankurDemoKB" # Replace with actual collection name
        project_for_query = "default" # Or specify a project if needed
        print(f"Attempting to get info for collection: '{collection_to_query}' in project: '{project_for_query or 'Default'}'")
        get_collection_info(collection_to_query, project_for_query)