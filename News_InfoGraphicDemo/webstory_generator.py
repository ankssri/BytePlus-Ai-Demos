import os
import time
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class WebstoryGenerator:
    """Class to handle webstory image generation using BytePlus ModelArk text-to-image API."""
    
    def __init__(self):
        """Initialize the generator with API details from environment variables."""
        self.api_key = os.getenv("ARK_API_KEY")
        self.api_endpoint = "https://ark.ap-southeast.bytepluses.com/api/v3/images/generations"
        self.model_id = os.getenv("ARK_SEEDREAM_MODEL_ID")  # Default model ID
        
        if not self.api_key:
            raise ValueError("Missing required API key for ModelArk text-to-image API")
    
    def generate_webstory_image(self, text, style="webstory"):
        """Generate a webstory image based on the provided text.
        
        Args:
            text (str): The text to generate an image for (title or bullet point).
            style (str): The style of image to generate ("webstory" or "title").
            
        Returns:
            str: URL of the generated image.
        """
        # Request headers
        req_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Clean input text by removing markdown and special formatting
        cleaned_text = text
        # Remove Visual prompt prefix
        if "**Visual prompt:**" in cleaned_text:
            cleaned_text = cleaned_text.split("**Visual prompt:**", 1)[1].strip()
        # Remove any remaining markdown formatting
        cleaned_text = cleaned_text.replace("**", "").replace("*", "").strip()
        # Remove any surrounding quotes
        cleaned_text = cleaned_text.strip('"').strip("'")  # Remove both single and double quotes
        
        # Adjust prompt based on style
        if style == "title":
            prompt = cleaned_text
            print(f"\n VLM Generating Title Image:\nStyle: {style}\nInput Text: {cleaned_text}\nPrompt: {prompt}\n")
        else:
            prompt = cleaned_text
            print(f"\n VLM Generating Story Image:\nStyle: {style}\nInput Text: {cleaned_text}\nPrompt: {prompt}\n")
        
        # Clean and truncate the prompt
        prompt = prompt.strip()
        if len(prompt) > 200:
            prompt = prompt[:200]
        
        # Track prompt token usage for image generation
        prompt_char_count = len(prompt)
        prompt_word_count = len(prompt.split())
        print(f"[TOKEN TRACKING] Image Generation - Prompt character count: {prompt_char_count}")
        print(f"[TOKEN TRACKING] Image Generation - Prompt word count: {prompt_word_count}")
        
        # Request body for ModelArk API
        req_body = {
            "model": self.model_id,
            "prompt": prompt,
            "response_format": "url",
            "size": "1024x1024",
            "guidance_scale": 3.0,
            "watermark": True
        }
        
        try:
            print(f"\nSending API request to ModelArk:\n")
            print(f"Request body:\n{req_body}\n")
            
            response = requests.post(
                self.api_endpoint,
                headers=req_headers,
                json=req_body
            )
            
            if response.status_code != 200:
                print(f"API Error Response:\n{response.text}\n")
                raise Exception(f"API request failed with status {response.status_code}: {response.text}")
            
            result = response.json()
            print(f"API Response:\n{result}\n")
            
            # Track image generation usage if available
            if "usage" in result:
                print(f"[TOKEN TRACKING] Image Generation - Usage information:")
                for key, value in result["usage"].items():
                    print(f"  - {key}: {value}")
            
            # Check if data contains image URLs
            if "data" not in result or not result["data"] or "url" not in result["data"][0]:
                raise Exception(f"API error: No image URL in response")
            
            return result["data"][0]["url"]
            
        except Exception as e:
            print(f"Error details: {str(e)}")
            raise Exception(f"Failed to generate webstory image: {str(e)}")