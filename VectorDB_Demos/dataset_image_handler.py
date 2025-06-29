import os
import io
import tempfile
import shutil
from PIL import Image
from datasets import load_dataset
import pandas as pd
import tos
import requests
import traceback  # For detailed error tracking
from dotenv import load_dotenv  # Add this import

# Load environment variables from .env file
load_dotenv()


class DatasetImageHandler:
    """Class for handling dataset download and image upload to BytePlus Object Storage"""
    
    def __init__(self, tos_access_key, tos_secret_key, tos_endpoint, tos_region, tos_bucket):
        self.tos_access_key = tos_access_key
        self.tos_secret_key = tos_secret_key
        self.tos_endpoint = tos_endpoint
        self.tos_region = tos_region
        self.tos_bucket = tos_bucket
        
    def load_dataset(self, dataset_name, split="train"):
        """Load dataset from Hugging Face"""
        try:
            print(f"Loading dataset {dataset_name} from Hugging Face...")
            dataset = load_dataset(dataset_name, split=split)
            df = dataset.to_pandas()
            print(f"Dataset loaded with {len(df)} records")
            print(f"Columns in dataset: {df.columns.tolist()}")
            
            # Print sample of image URLs to verify format
            if 'image' in df.columns:
                print(f"Sample image value: {df['image'].iloc[0]}")
                print(f"Image column data type: {type(df['image'].iloc[0])}")
            
            return df
        except Exception as e:
            print(f"ERROR in load_dataset: {e}")
            traceback.print_exc()
            return pd.DataFrame()
    
    def download_images_to_local(self, df, output_dir):
        """Download images from URLs in the dataset to a local folder"""
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Create a mapping of image paths to product IDs
        image_paths = {}
        
        for idx, row in df.iterrows():
            try:
                if 'image' not in row:
                    print(f"Row {idx} does not have 'image' column")
                    continue
                    
                if row['image'] is None:
                    print(f"Row {idx} has None value for 'image'")
                    continue
                
                # Print the type and value of the image field for debugging
                print(f"Row {idx} image type: {type(row['image'])}, value: {row['image'][:100] if isinstance(row['image'], str) else 'non-string'}")
                
                # Handle string URLs
                if isinstance(row['image'], str):
                    # Create a unique filename for each image
                    product_id = row.get('id', idx)
                    filename = f"product_{product_id}.jpg"
                    filepath = os.path.join(output_dir, filename)
                    
                    # Download image from URL
                    print(f"Downloading from URL: {row['image']}")
                    response = requests.get(row['image'], timeout=10)
                    if response.status_code == 200:
                        # Save the image to file
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        
                        # Store the mapping of image path to product ID
                        image_paths[filepath] = product_id
                        
                        print(f"Downloaded image to {filepath}")
                    else:
                        print(f"Failed to download image: HTTP {response.status_code}")
                else:
                    print(f"Row {idx} has non-string image value, skipping")
            except Exception as e:
                print(f"ERROR in download_images_to_local for row {idx}: {e}")
                traceback.print_exc()
        
        print(f"Downloaded {len(image_paths)} images successfully")
        return image_paths
    
    def upload_images_to_tos(self, local_dir):
        """Upload images from local directory to BytePlus Object Storage"""
        # Dictionary to store TOS paths
        tos_paths = {}
        
        try:
            # Check if directory exists and has files
            if not os.path.exists(local_dir):
                print(f"ERROR: Local directory {local_dir} does not exist")
                return {}
                
            files = os.listdir(local_dir)
            print(f"Found {len(files)} files in {local_dir}")
            
            if len(files) == 0:
                print(f"ERROR: No files found in {local_dir}")
                return {}
            
            # Initialize TOS client
            print(f"Initializing TOS client with endpoint {self.tos_endpoint}, region {self.tos_region}")
            tos_client = tos.TosClientV2(self.tos_access_key, self.tos_secret_key, 
                                         self.tos_endpoint, self.tos_region)
            
            # Test bucket access
            try:
                print(f"Testing access to bucket {self.tos_bucket}")
                # Try to list objects to verify bucket access
                tos_client.list_objects(self.tos_bucket, max_keys=1)
                print(f"Successfully accessed bucket {self.tos_bucket}")
            except Exception as e:
                print(f"ERROR accessing bucket {self.tos_bucket}: {e}")
                traceback.print_exc()
                return {}
            
            def upload_dir(root_dir):
                file_list = os.listdir(root_dir)
                for item in file_list:
                    path = os.path.join(root_dir, item)
                    if os.path.isdir(path):
                        upload_dir(path)
                    
                    if os.path.isfile(path):
                        # Create object key (relative path from local_dir)
                        rel_path = os.path.relpath(path, local_dir)
                        object_key = f"fashion_products/{rel_path}"
                        
                        # Upload file to TOS
                        try:
                            print(f"Uploading {path} to {object_key}")
                            tos_client.put_object_from_file(self.tos_bucket, object_key, path)
                            
                            # Store TOS path
                            tos_path = f"tos://{self.tos_bucket}/{object_key}"
                            tos_paths[path] = tos_path
                            
                            print(f"Uploaded {path} to {tos_path}")
                        except Exception as e:
                            print(f"ERROR uploading {path}: {e}")
                            traceback.print_exc()
            
            upload_dir(local_dir)
            print(f"Uploaded {len(tos_paths)} files to TOS")
            return tos_paths
            
        except tos.exceptions.TosClientError as e:
            print(f'Failed with TOS client error, message: {e.message}, cause: {e.cause}')
            traceback.print_exc()
        except tos.exceptions.TosServerError as e:
            print(f'Failed with TOS server error, code: {e.code}')
            print(f'Error with request id: {e.request_id}')
            print(f'Error with message: {e.message}')
            print(f'Error with http code: {e.status_code}')
            print(f'Error with ec: {e.ec}')
            print(f'Error with request url: {e.request_url}')
            traceback.print_exc()
        except Exception as e:
            print(f'Failed with unknown error: {e}')
            traceback.print_exc()
        
        return {}
    
    def update_dataframe_with_tos_paths(self, df, image_tos_paths):
        """Update dataframe with TOS paths for images"""
        try:
            # Create a new column for TOS paths
            df['image_tos_path'] = None
            
            if len(image_tos_paths) == 0:
                print("WARNING: No TOS paths to update in dataframe")
                return df
            
            updated_count = 0
            for idx, row in df.iterrows():
                product_id = row.get('id', idx)
                
                # Look for the TOS path in our mapping
                for local_path, tos_path in image_tos_paths.items():
                    if f"product_{product_id}.jpg" in local_path:
                        df.at[idx, 'image_tos_path'] = tos_path
                        updated_count += 1
                        break
            
            print(f"Updated {updated_count} rows with TOS paths")
            return df
        except Exception as e:
            print(f"ERROR in update_dataframe_with_tos_paths: {e}")
            traceback.print_exc()
            return df
    
    def process_dataset(self, dataset_name, temp_dir=None):
        """Process the dataset: download, upload to TOS, and update dataframe"""
        # Create a temporary directory if not provided
        if temp_dir is None:
            temp_dir = os.path.join(os.getcwd(), "fashion_images_temp")
        
        try:
            print(f"=== STEP 1: LOADING DATASET ===")
            # Load dataset
            df = self.load_dataset(dataset_name)
            if df.empty:
                print("ERROR: Failed to load dataset, exiting")
                return None
            
            print(f"\n=== STEP 2: DOWNLOADING IMAGES ===")
            # Download images to local folder
            print(f"Downloading images to {temp_dir}...")
            image_paths = self.download_images_to_local(df, temp_dir)
            if not image_paths:
                print("ERROR: Failed to download any images, exiting")
                return None
            
            print(f"\n=== STEP 3: UPLOADING IMAGES TO TOS ===")
            # Upload images to BytePlus Object Storage
            print(f"Uploading images to BytePlus Object Storage...")
            image_tos_paths = self.upload_images_to_tos(temp_dir)
            if not image_tos_paths:
                print("ERROR: Failed to upload images to TOS, exiting")
                return None
            
            print(f"\n=== STEP 4: UPDATING DATAFRAME ===")
            # Update dataframe with TOS paths
            df = self.update_dataframe_with_tos_paths(df, image_tos_paths)
            
            # Save the processed dataframe to CSV
            output_csv = "fashion_products_with_tos_paths.csv"
            df.to_csv(output_csv, index=False)
            print(f"Saved processed dataset to {output_csv}")
            
            return df
            
        finally:
            # Clean up temporary directory
            if os.path.exists(temp_dir):
                print(f"Cleaning up temporary directory {temp_dir}...")
                shutil.rmtree(temp_dir)

if __name__ == "__main__":
    # BytePlus Object Storage credentials from .env file
    TOS_ACCESS_KEY = os.getenv("TOS_ACCESS_KEY")
    TOS_SECRET_KEY = os.getenv("TOS_SECRET_KEY")
    TOS_ENDPOINT = os.getenv("TOS_ENDPOINT", "tos-ap-southeast-1.bytepluses.com")
    TOS_REGION = os.getenv("TOS_REGION", "ap-southeast-1")
    TOS_BUCKET = os.getenv("TOS_BUCKET", "ankurdemo")
    
    # Ensure the TOS SDK is installed
    try:
        import tos
    except ImportError:
        print("Installing BytePlus TOS SDK...")
        os.system("pip install tos")
        import tos
    
    # Create instance of DatasetImageHandler
    handler = DatasetImageHandler(
        TOS_ACCESS_KEY, TOS_SECRET_KEY, TOS_ENDPOINT, TOS_REGION, TOS_BUCKET
    )
    
    # Process the dataset
    handler.process_dataset("mecha2019/fashion-product-images-small")