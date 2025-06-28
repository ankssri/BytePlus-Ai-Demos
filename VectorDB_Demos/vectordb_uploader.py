from volcengine.viking_db import *
import random
import asyncio
import pandas as pd
import math
import os
import time

class VectorDBUploader:
    """Class for uploading data to VectorDB"""
    
    def __init__(self, vikingdb_service, collection_name):
        self.vikingdb_service = vikingdb_service
        self.collection_name = collection_name
    
    def gen_random_vector(self, dim):
        """Generate a random vector of specified dimension"""
        return [random.random() - 0.5 for _ in range(dim)]
    
    async def batch_upsert_data(self, df, batch_size=10, vector_dim=512, delay_seconds=2):
        """Insert data into VikingDB with TOS image paths"""
        collection = await self.vikingdb_service.async_get_collection(self.collection_name)
        total_records = len(df)
        num_batches = math.ceil(total_records / batch_size)
        
        for i in range(num_batches):
            start_idx = i * batch_size
            end_idx = min((i + 1) * batch_size, total_records)
            batch_df = df[start_idx:end_idx]
            
            data_batch = []
            for idx, row in batch_df.iterrows():
                # Create field dictionary with all available columns
                field = {
                    "vector": self.gen_random_vector(vector_dim),
                }
                
                # Add image path if available
                if 'image' in row and pd.notna(row['image']):
                    field['image'] = row['image']
                
                # Add all available text fields from the dataset
                for col in row.index:
                    if col in ['image']:
                        continue  # Skip the image column, we've already handled it
                    elif col in ['id', 'productDisplayName', 'gender', 'masterCategory', 
                               'subCategory', 'articleType', 'baseColour', 'season', 
                               'year', 'usage']:
                        if pd.notna(row[col]):
                            # Convert to appropriate type based on the column
                            if col in ['id', 'year']:
                                field[col] = int(row[col]) if isinstance(row[col], (int, float)) else 0
                            else:
                                field[col] = str(row[col])
                
                data_batch.append(Data(field))
            
            # Implement retry logic with exponential backoff
            max_retries = 5
            retry_count = 0
            retry_delay = delay_seconds
            
            while retry_count < max_retries:
                try:
                    await collection.async_upsert_data(data_batch)
                    print(f"Batch {i+1}/{num_batches} completed. Records {start_idx+1} to {end_idx} processed.")
                    
                    # Add delay between batches to avoid rate limiting
                    if i < num_batches - 1:  # No need to delay after the last batch
                        print(f"Waiting {delay_seconds} seconds before next batch...")
                        await asyncio.sleep(delay_seconds)
                    
                    # If successful, break out of retry loop
                    break
                    
                except Exception as e:
                    if "token usage has reached the maximum limit" in str(e):
                        retry_count += 1
                        print(f"Rate limit exceeded. Retry {retry_count}/{max_retries} after {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        # Exponential backoff
                        retry_delay *= 2
                    else:
                        # If it's not a rate limit error, re-raise it
                        raise

            # If we've exhausted all retries, report the error
            if retry_count >= max_retries:
                print(f"Failed to process batch {i+1} after {max_retries} retries. Continuing with next batch.")

async def main():
    # VikingDB credentials
    vikingdb_service = VikingDBService("api-vikingdb.mlp.ap-mya.byteplus.com", "ap-southeast-1")
    vikingdb_service.set_ak("<BytePlus API Key>")
    vikingdb_service.set_sk("<BytePlus Secret Key>")
    
    # Create instance of VectorDBUploader
    uploader = VectorDBUploader(
        vikingdb_service, "Ankur_Product_Image_Collection"
    )
    
    # Load the processed dataset
    csv_path = "fashion_products_with_tos_paths.csv"
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found. Please run dataset_image_handler.py first.")
        return
    
    df = pd.read_csv(csv_path)
    print(f"Loaded processed dataset with {len(df)} records")
    
    # Ask user for confirmation before proceeding
    print("\nWARNING: You are about to upload data to VectorDB.")
    print("This operation may be rate-limited by the service.")
    print("Recommended settings:")
    print("- Batch size: 10 (smaller to reduce load)")
    print("- Delay between batches: 2 seconds (to avoid rate limiting)")
    
    # Get user input for batch size and delay
    try:
        batch_size = int(input("Enter batch size (default: 10): ") or 10)
        delay = float(input("Enter delay between batches in seconds (default: 2): ") or 2)
    except ValueError:
        print("Invalid input. Using default values: batch_size=10, delay=2")
        batch_size = 10
        delay = 2
    
    # Upload the data to VectorDB with user-specified parameters
    await uploader.batch_upsert_data(df, batch_size=batch_size, delay_seconds=delay)
    
    print("All data has been uploaded to VectorDB successfully!")

if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())