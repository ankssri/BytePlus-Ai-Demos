from volcengine.viking_db import *
import asyncio
import pandas as pd
import math
import random
import time

# Initialize VikingDB service
vikingdb_service = VikingDBService("api-vikingdb.mlp.ap-mya.byteplus.com", "ap-southeast-1")
vikingdb_service.set_ak("<BytePlus API Key>")
vikingdb_service.set_sk("<BytePlus Secret Key>")

async def batch_upsert_data(df, batch_size=10, delay_seconds=2):
    # Get the collection
    collection = await vikingdb_service.async_get_collection("Ankur_NewsRAG_Collection")
    total_records = len(df)
    num_batches = math.ceil(total_records / batch_size)
    
    for i in range(num_batches):
        start_idx = i * batch_size
        end_idx = min((i + 1) * batch_size, total_records)
        batch_df = df[start_idx:end_idx]
        
        data_batch = []
        for idx, row in batch_df.iterrows():
            # Create field dictionary with all required fields
            field = {
                "id": int(idx),  # Using index as ID
                "headline": str(row['headline']),
                "summary": str(row['summary']),
                "category": str(row['category']),
                "url": str(row['url']),
                "imageurl": str(row['imageurl']),
                "language": str(row['language'])
                # No need to add vector field as BytePlus VectorDB will handle vectorization
            }
            data_batch.append(Data(field))
        
        # Implement retry logic with exponential backoff
        max_retries = 5
        retry_count = 0
        retry_delay = delay_seconds
        
        while retry_count < max_retries:
            try:
                # Upload batch to VectorDB
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
                    # If it's not a rate limit error, print it and continue
                    print(f"Error processing batch {i+1}: {str(e)}")
                    break
        
        # If we've exhausted all retries, report the error
        if retry_count >= max_retries:
            print(f"Failed to process batch {i+1} after {max_retries} retries. Continuing with next batch.")

async def main():
    # Read the CSV file with UTF-8-SIG encoding
    csv_path = "news_data/all_languages_news_data.csv"
    print(f"Loading data from {csv_path}")
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    
    # Ask user for confirmation before proceeding
    print(f"\nWARNING: You are about to upload {len(df)} records to VectorDB.")
    print("This operation may be rate-limited by the service.")
    print("Recommended settings:")
    print("- Batch size: 10 (smaller to reduce load)")
    print("- Delay between batches: 5 seconds (to avoid rate limiting)")
    
    # Get user input for batch size and delay
    try:
        batch_size = int(input("Enter batch size (default: 10): ") or 10)
        delay = float(input("Enter delay between batches in seconds (default: 5): ") or 5)
    except ValueError:
        print("Invalid input. Using default values: batch_size=10, delay=5")
        batch_size = 10
        delay = 5
    
    # Process and upload the data
    print(f"Uploading {len(df)} records to VectorDB with batch size {batch_size} and {delay}s delay")
    await batch_upsert_data(df, batch_size=batch_size, delay_seconds=delay)
    print("All data has been uploaded successfully!")

if __name__ == "__main__":
    asyncio.run(main())