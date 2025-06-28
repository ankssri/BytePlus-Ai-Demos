"""Module for infographic generation using BytePlus text-to-image API."""

import os
import time
import random
import hashlib
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class InfographicGenerator:
    """Class to handle infographic generation using BytePlus text-to-image API."""
    
    def __init__(self):
        """Initialize the generator with API details from environment variables."""
        self.api_key = os.getenv("CV_API_KEY")
        self.api_secret = os.getenv("CV_API_SECRET")
        self.api_endpoint = os.getenv("CV_API_ENDPOINT")
        self.req_key = os.getenv("CV_REQ_KEY")
        
        if not all([self.api_key, self.api_secret, self.api_endpoint, self.req_key]):
            raise ValueError("Missing required environment variables for text-to-image API")
    
    def _generate_signature(self, nonce, timestamp):
        """Generate signature for API authentication.
        
        Args:
            nonce (int): Random nonce value.
            timestamp (int): Current timestamp.
            
        Returns:
            str: Generated signature.
        """
        keys = [str(nonce), self.api_secret, str(timestamp)]
        keys.sort()
        key_str = ''.join(keys).encode('utf-8')
        signature = hashlib.sha1(key_str).hexdigest()
        return signature.lower()
    
    def generate_infographic(self, article_title):
        """Generate an infographic based on the article title."""
        #print(f" --- Image_generator.py --- Generating infographic for title: {article_title}")  # Debug title value
        timestamp = int(time.time())
        nonce = random.randint(0, (1 << 31) - 1)
        
        # Parameters for signature
        req_params = {
            "api_key": self.api_key,
            "timestamp": str(timestamp),
            "nonce": str(nonce),
            "sign": self._generate_signature(nonce, timestamp)
        }
        
        # Request headers
        req_headers = {
            "Content-Type": "application/json"
        }
        
        # Clean the title before API call
        cleaned_title = article_title.strip('*')
        print(f" --- Image_generator.py --- Generating infographic for title: {cleaned_title}")
        
        # Request body
        req_body = {
            "req_key": self.req_key,
            "prompt": cleaned_title,  # Use cleaned title
            "return_url": True,
            "logo_info": {
                "add_logo": True,
                "position": 0,
                "language": 0,
                "opacity": 0.3,
                "logo_text_content": "@BytePlus 2025"
            }
        }
        
        try:
            response = requests.post(
                self.api_endpoint,
                params=req_params,
                headers=req_headers,
                json=req_body
            )
            response.raise_for_status()
            
            result = response.json()
            
            if result["code"] != 10000 or not result["data"]["image_urls"]:
                raise Exception(f"API error: {result['message']}")
            
            # Return the first image URL
            return result["data"]["image_urls"][0]
            
        except Exception as e:
            raise Exception(f"Failed to generate infographic: {str(e)}")