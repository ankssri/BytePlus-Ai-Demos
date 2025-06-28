import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class PromptGenerator:
    """Class to enhance webstory prompts using BytePlus LLM API."""
    
    def __init__(self):
        """Initialize the generator with API details from environment variables."""
        self.api_key = os.getenv("ARK_API_KEY")
        self.api_endpoint = os.getenv("ARK_API_ENDPOINT")
        self.model_id = os.getenv("ARK_MODEL_ID")
        
        if not all([self.api_key, self.api_endpoint, self.model_id]):
            raise ValueError("Missing required environment variables for LLM API")
    
    def enhance_title_prompt(self, title):
        """Enhance the title prompt for better image generation.
        
        Args:
            title (str): The original webstory title.
            
        Returns:
            str: Enhanced prompt for image generation.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Calculate input token length (approximate)
        input_tokens = len(title.split())
        print(f"\n[TOKEN TRACKING] Title Prompt Enhancement - Input tokens (approx): {input_tokens}")
        
        prompt_instruction = (
            "Convert this title into a visual description. "
            "Focus on key visual elements only. "
            "Keep it under 150 characters and as one complete sentence."
            "Make sure that there is no single or double quotes used in the response text."
        )
        
        system_tokens = len(prompt_instruction.split())
        print(f"[TOKEN TRACKING] Title Prompt Enhancement - System prompt tokens (approx): {system_tokens}")
        
        user_content = "I need prompt for generating cover image for news article title : "+ title
        user_tokens = len(user_content.split())
        print(f"[TOKEN TRACKING] Title Prompt Enhancement - User message tokens (approx): {user_tokens}")
        
        payload = {
            "model": self.model_id,
            "messages": [
                {
                    "role": "system",
                    "content": prompt_instruction
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ]
        }
        
        try:
            response = requests.post(self.api_endpoint, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            # Extract token usage information if available
            if "usage" in result:
                print(f"[TOKEN TRACKING] Title Prompt Enhancement - Actual token usage:")
                print(f"  - Prompt tokens: {result['usage'].get('prompt_tokens', 'N/A')}")
                print(f"  - Completion tokens: {result['usage'].get('completion_tokens', 'N/A')}")
                print(f"  - Total tokens: {result['usage'].get('total_tokens', 'N/A')}")
            
            enhanced_prompt = result["choices"][0]["message"]["content"]
            output_tokens = len(enhanced_prompt.split())
            print(f"[TOKEN TRACKING] Title Prompt Enhancement - Output tokens (approx): {output_tokens}")
            
            print(f"\n PG.py Title Prompt Enhancement:\nOriginal: {title}\nEnhanced: {enhanced_prompt}\n")
            return enhanced_prompt.strip()
            
        except Exception as e:
            raise Exception(f"Failed to enhance title prompt: {str(e)}")
    
    def enhance_bullet_prompt(self, bullet_point):
        """Enhance the bullet point prompt for better image generation.
        
        Args:
            bullet_point (str): The original bullet point.
            
        Returns:
            str: Enhanced prompt for image generation.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Calculate input token length (approximate)
        input_tokens = len(bullet_point.split())
        print(f"\n[TOKEN TRACKING] Bullet Prompt Enhancement - Input tokens (approx): {input_tokens}")
        
        prompt_instruction = (
            "Convert this news bullet point into a visual description. "
            "Focus on key visual elements only. "
            "Keep it under 150 characters and as one complete sentence."
            "Make sure that there is no single or double quotes used in the response text."
        )
        
        system_tokens = len(prompt_instruction.split())
        print(f"[TOKEN TRACKING] Bullet Prompt Enhancement - System prompt tokens (approx): {system_tokens}")
        
        user_content = "I need prompt for generating cover image for news article : " + bullet_point
        user_tokens = len(user_content.split())
        print(f"[TOKEN TRACKING] Bullet Prompt Enhancement - User message tokens (approx): {user_tokens}")
        
        payload = {
            "model": self.model_id,
            "messages": [
                {
                    "role": "system",
                    "content": prompt_instruction
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ]
        }
        
        try:
            response = requests.post(self.api_endpoint, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            # Extract token usage information if available
            if "usage" in result:
                print(f"[TOKEN TRACKING] Bullet Prompt Enhancement - Actual token usage:")
                print(f"  - Prompt tokens: {result['usage'].get('prompt_tokens', 'N/A')}")
                print(f"  - Completion tokens: {result['usage'].get('completion_tokens', 'N/A')}")
                print(f"  - Total tokens: {result['usage'].get('total_tokens', 'N/A')}")
            
            enhanced_prompt = result["choices"][0]["message"]["content"]
            output_tokens = len(enhanced_prompt.split())
            print(f"[TOKEN TRACKING] Bullet Prompt Enhancement - Output tokens (approx): {output_tokens}")
            
            print(f"\n PG.py Bullet Point Prompt Enhancement:\nOriginal: {bullet_point}\nEnhanced: {enhanced_prompt}\n")
            return enhanced_prompt.strip()
            
        except Exception as e:
            raise Exception(f"Failed to enhance bullet point prompt: {str(e)}")