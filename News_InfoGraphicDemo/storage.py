"""Module for saving images and articles to BytePlus object storage."""

import os
import requests
import tempfile
from datetime import datetime
import tos
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class StorageManager:
    """Class to handle saving images and articles to BytePlus object storage."""
    
    def __init__(self):
        """Initialize the storage manager with API details from environment variables."""
        # BytePlus Object Storage credentials
        self.access_key = os.getenv("TOS_ACCESS_KEY")
        self.secret_key = os.getenv("TOS_SECRET_KEY")
        self.endpoint = os.getenv("TOS_ENDPOINT", "tos-ap-southeast-1.bytepluses.com")
        self.region = os.getenv("TOS_REGION", "ap-southeast-1")
        self.bucket_name = os.getenv("TOS_BUCKET_NAME", "ankurdemo")
        self.object_key_prefix = os.getenv("TOS_OBJECT_KEY_PREFIX", "vectorDB_ProductImages")
        
        if not all([self.access_key, self.secret_key]):
            raise ValueError("Missing required environment variables for BytePlus Object Storage")
        
        # Create TOS client
        self.client = tos.TosClientV2(
            self.access_key,
            self.secret_key,
            self.endpoint,
            self.region
        )
    
    def _download_image(self, image_url):
        """Download image from URL to a temporary file.
        
        Args:
            image_url (str): URL of the image to download.
            
        Returns:
            str: Path to the temporary file containing the image.
            
        Raises:
            Exception: If downloading fails.
        """
        try:
            response = requests.get(image_url, stream=True)
            response.raise_for_status()
            
            # Create a temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            temp_file_path = temp_file.name
            
            # Write the image content to the temporary file
            with open(temp_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return temp_file_path
            
        except Exception as e:
            raise Exception(f"Failed to download image: {str(e)}")
    
    def save_image(self, image_url, article_title):
        """Save the image to BytePlus object storage.
        
        Args:
            image_url (str): URL of the image to save.
            article_title (str): Title of the article associated with the image.
            
        Returns:
            str: URL of the saved image in object storage.
            
        Raises:
            Exception: If saving fails.
        """
        try:
            # Generate a unique object key based on timestamp and article title
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            # Clean article title to use as part of the filename
            clean_title = ''.join(c if c.isalnum() else '_' for c in article_title)[:50]
            object_key = f"{self.object_key_prefix}/images/{timestamp}_{clean_title}.jpg"
            
            # Download the image to a temporary file
            temp_file_path = self._download_image(image_url)
            
            try:
                # Upload the image to BytePlus Object Storage
                self.client.put_object_from_file(
                    self.bucket_name,
                    object_key,
                    temp_file_path
                )
                
                # Generate a URL for the uploaded image
                # Note: This is a simple URL construction, you might need to adjust based on your actual setup
                storage_url = f"https://{self.bucket_name}.{self.endpoint}/{object_key}"
                
                return storage_url
                
            finally:
                # Clean up the temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except tos.exceptions.TosClientError as e:
            raise Exception(f"Client error saving image: {e.message}, cause: {e.cause}")
        except tos.exceptions.TosServerError as e:
            raise Exception(f"Server error saving image: {e.message}, request ID: {e.request_id}")
        except Exception as e:
            raise Exception(f"Failed to save image: {str(e)}")
    
    def save_article(self, article_text, article_title, summary_points):
        """Save the article and its summary to BytePlus object storage.
        
        Args:
            article_text (str): Full text of the article.
            article_title (str): Title of the article.
            summary_points (list): List of summary bullet points.
            
        Returns:
            str: URL of the saved article in object storage.
            
        Raises:
            Exception: If saving fails.
        """
        try:
            # Generate a unique object key based on timestamp and article title
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            # Clean article title to use as part of the filename
            clean_title = ''.join(c if c.isalnum() else '_' for c in article_title)[:50]
            object_key = f"{self.object_key_prefix}/articles/{timestamp}_{clean_title}.txt"
            
            # Create a temporary file with the article content
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".txt") as temp_file:
                temp_file_path = temp_file.name
                
                # Write article title, content, and summary to the file
                temp_file.write(f"Title: {article_title}\n\n")
                temp_file.write(f"Content:\n{article_text}\n\n")
                temp_file.write("Summary:\n")
                for point in summary_points:
                    temp_file.write(f"- {point}\n")
            
            try:
                # Upload the article to BytePlus Object Storage
                self.client.put_object_from_file(
                    self.bucket_name,
                    object_key,
                    temp_file_path
                )
                
                # Generate a URL for the uploaded article
                # Note: This is a simple URL construction, you might need to adjust based on your actual setup
                storage_url = f"https://{self.bucket_name}.{self.endpoint}/{object_key}"
                
                return storage_url
                
            finally:
                # Clean up the temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except tos.exceptions.TosClientError as e:
            raise Exception(f"Client error saving article: {e.message}, cause: {e.cause}")
        except tos.exceptions.TosServerError as e:
            raise Exception(f"Server error saving article: {e.message}, request ID: {e.request_id}")
        except Exception as e:
            raise Exception(f"Failed to save article: {str(e)}")