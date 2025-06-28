import hashlib
import time
import random
import requests
from requests.exceptions import RequestException


def gen_sign(nonce, security_key, timestamp):
    keys = [str(nonce), str(security_key), str(timestamp)]
    keys.sort()
    key_str = ''.join(keys).encode('utf-8')
    signature = hashlib.sha1(key_str).hexdigest()
    return signature.lower()


if __name__ == '__main__':
    req_url = 'https://cv-api.bytedance.com/api/common/v2/process'
    timestamp = int(time.time())
    nonce = random.randint(0, (1<<31)-1)
    
    # API key and security key are different
    api_key = "your trial api key"
    security_key = "your trial security key"  # sk for signature generation
    
    req_params = { # Add the parameters required for signature into the Query part
        "api_key": api_key,
        "timestamp": str(timestamp),
        "nonce": str(nonce),
        "sign": gen_sign(nonce, security_key, timestamp)
    }
    req_headers = {
        "Content-Type": "application/json"
    }
    
    # Use publicly accessible image URLs instead
    # You can replace these with your own publicly accessible images
    req_body = {
        "req_key": "dressing_diffusion",
        "model": {
            "id": "1",
            "url": "https://cdn.shopify.com/s/files/1/0577/5523/8456/files/Model.png"
        },
        "garment": {
            "id": "1",
            "data": [
                {
                    "url": "https://cdn.shopify.com/s/files/1/0577/5523/8456/files/clothing.png"
                }
            ]
        },
        "return_url": True,
        "logo_info": {
            "add_logo": False,
            "position": 0,
            "language": 0,
            "logo_text_content": "watermark"
        }
    }

    # Add error handling to see the actual response content
    # Add retry logic with increased timeout
    max_retries = 3
    retry_delay = 5  # seconds
    
    for attempt in range(max_retries):
        try:
            # Increase timeout to 120 seconds to handle potential slow connections
            resp = requests.post(req_url, params=req_params, headers=req_headers, json=req_body, timeout=120)
            resp.raise_for_status()  # Raise an exception for 4XX/5XX responses
            json_response = resp.json()
            print(f"Status Code: {resp.status_code}")
            print(f"Response: {json_response}")
            break  # Success, exit the retry loop
        except (RequestException, ValueError) as e:
            print(f"Attempt {attempt+1}/{max_retries} failed: {str(e)}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"Error: All {max_retries} attempts failed.")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"Status Code: {e.response.status_code}")
                    print(f"Response content: {e.response.text}")
