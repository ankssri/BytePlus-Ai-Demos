"""Module for article summarization using BytePlus LLM API."""

import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ArticleSummarizer:
    """Class to handle article summarization using BytePlus LLM API."""
    
    def __init__(self):
        """Initialize the summarizer with API details from environment variables."""
        self.api_key = os.getenv("ARK_API_KEY")
        self.api_endpoint = os.getenv("ARK_API_ENDPOINT")
        self.model_id = os.getenv("ARK_MODEL_ID")
        
        if not all([self.api_key, self.api_endpoint, self.model_id]):
            raise ValueError("Missing required environment variables for LLM API")
    
    def summarize_article(self, article_text):
        """Summarize the given article text using BytePlus LLM API.
        
        Args:
            article_text (str): The news article text to summarize.
            
        Returns:
            list: A list of bullet points summarizing the article.
            
        Raises:
            Exception: If the API request fails.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Calculate input token length (approximate)
        input_tokens = len(article_text.split())
        print(f"\n[TOKEN TRACKING] Summarizer - Input tokens (approx): {input_tokens}")
        
        system_prompt = "You are an expert in summarizing news article and generating article title. Return title and summary of article in maximum 3 bullet points."
        system_tokens = len(system_prompt.split())
        print(f"[TOKEN TRACKING] Summarizer - System prompt tokens (approx): {system_tokens}")
        
        payload = {
            "model": self.model_id,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": article_text
                }
            ]
        }
        
        try:
            response = requests.post(self.api_endpoint, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            print("\n Summarizer.py LLM API Response:")
            print("==================")
            print(result)
            print("==================\n")
            
            # Extract token usage information if available
            if "usage" in result:
                print(f"[TOKEN TRACKING] Summarizer - Actual token usage:")
                print(f"  - Prompt tokens: {result['usage'].get('prompt_tokens', 'N/A')}")
                print(f"  - Completion tokens: {result['usage'].get('completion_tokens', 'N/A')}")
                print(f"  - Total tokens: {result['usage'].get('total_tokens', 'N/A')}")
            
            summary_text = result["choices"][0]["message"]["content"]
            output_tokens = len(summary_text.split())
            print(f"[TOKEN TRACKING] Summarizer - Output tokens (approx): {output_tokens}")
            
            print("Extracted Content:")
            print("==================")
            print(summary_text)
            print("==================\n")
            
            # Split the response into lines
            lines = summary_text.split('\n')
            
            # Extract title and bullet points
            title = ""
            bullet_points = []
            
            for line in lines:
                line = line.strip()
                if 'Title:' in line:
                    title = line.replace('**Title:', '').replace('**', '').strip().strip('"')
                elif line.startswith('-'):
                    bullet_points.append(line.lstrip('-').strip().replace('**', '').strip())
            
            print("Processed Output:")
            print("==================")
            print(f"Title: {title}")
            print("Bullet Points:")
            for point in bullet_points:
                print(f"- {point}")
            print("Summarizer.py End ==================\n")
            
            return title, bullet_points
            
        except Exception as e:
            raise Exception(f"Failed to summarize article: {str(e)}")