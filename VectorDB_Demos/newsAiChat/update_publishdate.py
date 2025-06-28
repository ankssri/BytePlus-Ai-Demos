from volcengine.viking_db import *
import asyncio
import random
from datetime import datetime, timedelta
import time

# Initialize VikingDB service
vikingdb_service = VikingDBService("api-vikingdb.mlp.ap-mya.byteplus.com", "ap-southeast-1")
vikingdb_service.set_ak("<BytePlus API Key>")
vikingdb_service.set_sk("<BytePlus Secret Key>")

# Define date range
START_DATE = datetime(2025, 5, 28, 0, 0, 0)  # May 28, 2025 00:00:00
END_DATE = datetime(2025, 5, 31, 23, 59, 59)  # May 31, 2025 23:59:59

# Generate a random date and time between START_DATE and END_DATE
def generate_random_date():
    time_delta = END_DATE - START_DATE
    random_seconds = random.randint(0, int(time_delta.total_seconds()))
    random_date = START_DATE + timedelta(seconds=random_seconds)
    # Format: DD-MM-YYYY HH:MM:SS
    return random_date.strftime("%d-%m-%Y %H:%M:%S")

# Update records in batches
async def update_records_in_batches(batch_size=100, delay_seconds=2):
    # Get the collection
    collection = vikingdb_service.get_collection("Ankur_NewsRAG_Collection")
    
    # Total number of records to update
    total_records = 11001
    num_batches = (total_records + batch_size - 1) // batch_size  # Ceiling division
    
    records_updated = 0
    
    print(f"Starting update of 'publishdate' field for {total_records} records...")
    
    for batch_num in range(1, num_batches + 1):
        start_id = (batch_num - 1) * batch_size + 1
        end_id = min(batch_num * batch_size, total_records)
        
        batch_data = []
        
        # Create update data for each record in the batch
        for record_id in range(start_id, end_id + 1):
            # Generate random publish date
            publish_date = generate_random_date()
            
            # Create field dictionary with ID and new publishdate field
            field = {
                "id": record_id,
                "publishdate": publish_date
            }
            
            batch_data.append(Data(field))
        
        # Implement retry logic with exponential backoff
        max_retries = 5
        retry_count = 0
        retry_delay = delay_seconds
        
        while retry_count < max_retries:
            try:
                # Update batch in VectorDB - remove await
                collection.update_data(batch_data)
                records_updated += len(batch_data)
                
                print(f"Batch {batch_num}/{num_batches} completed. Records {start_id} to {end_id} updated.")
                print(f"Progress: {records_updated}/{total_records} records updated ({(records_updated/total_records*100):.2f}%)")
                
                # Add delay between batches to avoid rate limiting
                if batch_num < num_batches:  # No need to delay after the last batch
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
                    print(f"Error processing batch {batch_num}: {str(e)}")
                    break
        
        # If we've exhausted all retries, report the error
        if retry_count >= max_retries:
            print(f"Failed to process batch {batch_num} after {max_retries} retries. Continuing with next batch.")
    
    print(f"\nUpdate completed! {records_updated}/{total_records} records updated with random publish dates.")

async def main():
    # Ask user for confirmation before proceeding
    print("\nWARNING: You are about to update the 'publishdate' field for 11001 records in VectorDB.")
    print("This operation may be rate-limited by the service.")
    print("Recommended settings:")
    print("- Batch size: 100 (smaller to reduce load)")
    print("- Delay between batches: 2 seconds (to avoid rate limiting)")
    
    # Get user input for batch size and delay
    try:
        batch_size = int(input("Enter batch size (default: 100): ") or 100)
        delay = float(input("Enter delay between batches in seconds (default: 2): ") or 2)
    except ValueError:
        print("Invalid input. Using default values: batch_size=100, delay=2")
        batch_size = 100
        delay = 2
    
    # Confirm with user
    confirm = input("\nReady to proceed? This will update all 11001 records. (y/n): ")
    if confirm.lower() != 'y':
        print("Operation cancelled.")
        return
    
    # Start the update process
    start_time = time.time()
    await update_records_in_batches(batch_size, delay)
    end_time = time.time()
    
    print(f"Total execution time: {(end_time - start_time):.2f} seconds")

if __name__ == "__main__":
    asyncio.run(main())