import os
import json
import tempfile
from datetime import datetime
import tos
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class WebstoryStorage:
    """Class to handle saving webstories to BytePlus object storage."""
    
    def __init__(self):
        """Initialize the storage manager with API details from environment variables."""
        self.access_key = os.getenv("TOS_ACCESS_KEY")
        self.secret_key = os.getenv("TOS_SECRET_KEY")
        self.endpoint = os.getenv("TOS_ENDPOINT", "tos-ap-southeast-1.bytepluses.com")
        self.region = os.getenv("TOS_REGION", "ap-southeast-1")
        self.bucket_name = os.getenv("TOS_BUCKET_NAME", "ankurdemo")
        self.object_key_prefix = os.getenv("TOS_OBJECT_KEY_PREFIX_NEWS", "webstories")
        
        if not all([self.access_key, self.secret_key]):
            raise ValueError("Missing required environment variables for BytePlus Object Storage")
        
        # Create TOS client
        self.client = tos.TosClientV2(
            self.access_key,
            self.secret_key,
            self.endpoint,
            self.region
        )
    
    def get_download_url(self, object_key):
        """Generate a pre-signed URL for downloading the webstory.
        
        Args:
            object_key (str): The object key in storage.
            
        Returns:
            str: Pre-signed URL for downloading the file.
        """
        try:
            # Generate a pre-signed URL that expires in 1 hour
            pre_signed_url_output = self.client.pre_signed_url(
                tos.HttpMethodType.Http_Method_Get,
                self.bucket_name,
                object_key
            )
            return pre_signed_url_output.signed_url
        except tos.exceptions.TosClientError as e:
            raise Exception(f"Failed to generate download URL: Client error - {e.message}")
        except tos.exceptions.TosServerError as e:
            raise Exception(f"Failed to generate download URL: Server error - {e.message} (Request ID: {e.request_id})")
        except Exception as e:
            raise Exception(f"Failed to generate download URL: {str(e)}")

    def save_webstory(self, html_content, title):
        """Save the webstory HTML to BytePlus object storage.
        
        Args:
            html_content (str): The HTML content of the webstory.
            title (str): The title of the webstory.
            
        Returns:
            str: URL of the saved webstory in object storage.
        """
        try:
            # Generate a unique object key
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            clean_title = ''.join(c if c.isalnum() else '_' for c in title)[:50]
            object_key = f"{self.object_key_prefix}/{timestamp}_{clean_title}.html"
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".html") as temp_file:
                temp_file_path = temp_file.name
                temp_file.write(html_content)
            
            try:
                # Upload to BytePlus Object Storage
                self.client.put_object_from_file(
                    self.bucket_name,
                    object_key,
                    temp_file_path
                )
                
                # Generate URL for the uploaded webstory
                storage_url = f"https://{self.bucket_name}.{self.endpoint}/{object_key}"
                download_url = self.get_download_url(object_key)
                return storage_url, download_url
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except Exception as e:
            raise Exception(f"Failed to save webstory: {str(e)}")