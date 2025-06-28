from volcengine.viking_db import *
import asyncio
import pandas as pd
import math
import os
import glob

# Initialize VikingDB service
vikingdb_service = VikingDBService("api-vikingdb.mlp.ap-mya.byteplus.com", "ap-southeast-1")
vikingdb_service.set_ak("<BytePlus API Key>")
vikingdb_service.set_sk("<BytePlus Secret Key>")

# Language code to full name mapping
LANGUAGE_MAPPING = {
    "hi": "hindi",
    "gu": "gujarati",
    "ta": "tamil",
    "te": "telugu",
    "ml": "malayalam",
    "mr": "marathi",
    "bn": "bengali",
    "kn": "kannada",
    "or": "oriya",
    "pa": "punjabi",
    "as": "assamese"  # Added this in case it's present in the data
}

# Global ID counter to ensure unique IDs across all language files
global_id_counter = 0

async def batch_upsert_data(df, language_code, batch_size=10, delay_seconds=5):
    global global_id_counter
    # Get the collection
    collection = await vikingdb_service.async_get_collection("Ankur_NewsRAG_Collection")
    
    # Limit to 1000 records per language
    df = df.head(1000)
    
    total_records = len(df)
    num_batches = math.ceil(total_records / batch_size)
    
    # Get full language name from code
    language_name = LANGUAGE_MAPPING.get(language_code, language_code)
    
    print(f"Processing {total_records} records for language: {language_name}")
    print(f"Starting with global ID: {global_id_counter + 1}")
    
    for i in range(num_batches):
        start_idx = i * batch_size
        end_idx = min((i + 1) * batch_size, total_records)
        batch_df = df[start_idx:end_idx]
        
        data_batch = []
        for _, row in batch_df.iterrows():
            # Increment the global ID counter for each record
            global_id_counter += 1
            
            # Create field dictionary with all required fields
            # In batch_upsert_data function:
            field = {
                "id": global_id_counter,
                "headline": str(row['headline']),  # Should have vector_index=true in collection schema
                "summary": str(row['summary']),    # Should have vector_index=true <mcsymbol name="Ankur_NewsRAG_Collection" filename="upload_news_dataset.py" path="/Users/bytedance/Documents/ByteDance/ModelArkDemo/VectorDB/newsAiChat/upload_news_dataset.py" startline="10" type="class"></mcsymbol>
                "category": str(row['category']),
                "url": str(row['url']),
                "imageurl": str(row['imageurl']),
                "language": language_name,  # Use the full language name
                "original_id": int(row['id'])  # Keep the original ID as a reference
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
                print(f"Batch {i+1}/{num_batches} completed. Records {start_idx+1} to {end_idx} processed for {language_name}.")
                print(f"Global ID range: {global_id_counter - len(data_batch) + 1} to {global_id_counter}")
                
                # Add delay between batches to avoid rate limiting
                if i < num_batches - 1:  # No need to delay after the last batch
                    print(f"Waiting {delay_seconds} seconds before next batch...")
                    await asyncio.sleep(delay_seconds)
                
                # If successful, break out of retry loop
                break
                
            except Exception as e:
                if "token usage has reached the maximum limit" in str(e) or "VikingDBException" in str(e):
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

async def process_language_file(file_path, batch_size, delay_seconds):
    # Extract language code from file name
    file_name = os.path.basename(file_path)
    language_code = file_name.split('_')[0]
    
    # Skip all_languages file as we're processing individual language files
    if language_code == "all":
        return
    
    print(f"\nProcessing file: {file_name}")
    
    try:
        # Read the CSV file with UTF-8-SIG encoding to handle BOM
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        
        # Process and upload the data
        await batch_upsert_data(df, language_code, batch_size, delay_seconds)
        
    except Exception as e:
        print(f"Error processing file {file_name}: {str(e)}")

async def main():
    global global_id_counter
    # Path to news data directory
    data_dir = "/Users/bytedance/Documents/ByteDance/ModelArkDemo/VectorDB/newsAiChat/news_data"
    
    # Get all CSV files in the directory
    csv_files = glob.glob(os.path.join(data_dir, "*_news_data.csv"))
    
    # Filter out all_languages file
    csv_files = [f for f in csv_files if "all_languages" not in f]
    
    print(f"Found {len(csv_files)} language-specific CSV files")
    
    # Ask user for confirmation before proceeding
    print(f"\nWARNING: You are about to upload up to 1000 records per language to VectorDB.")
    print("This operation may be rate-limited by the service.")
    print("Recommended settings:")
    print("- Batch size: 10 (smaller to reduce load)")
    print("- Delay between batches: 5 seconds (to avoid rate limiting)")
    
    # Get user input for batch size and delay
    try:
        batch_size = int(input("Enter batch size (default: 10): ") or 10)
        delay = float(input("Enter delay between batches in seconds (default: 5): ") or 5)
        
        # Option to set starting ID
        start_id = input("Enter starting ID (default: 0, press Enter to use default): ")
        if start_id.strip():
            global_id_counter = int(start_id)
    except ValueError:
        print("Invalid input. Using default values: batch_size=10, delay=5, start_id=0")
        batch_size = 10
        delay = 5
    
    # Process each language file
    for file_path in csv_files:
        await process_language_file(file_path, batch_size, delay)
    
    print(f"\nAll data has been uploaded successfully! Total records: {global_id_counter}")

if __name__ == "__main__":
    asyncio.run(main())