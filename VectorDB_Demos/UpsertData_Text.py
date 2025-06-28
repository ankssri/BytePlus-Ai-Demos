from volcengine.viking_db import *
import random
import asyncio
import pandas as pd
import math

vikingdb_service = VikingDBService("api-vikingdb.mlp.ap-mya.byteplus.com", "ap-southeast-1")
vikingdb_service.set_ak("<BytePlus API Key")
vikingdb_service.set_sk("<BytePlus Secret Key>")

def gen_random_vector(dim):    
    return [random.random() - 0.5 for _ in range(dim)] 

async def batch_upsert_data(df, batch_size=100):
    collection = await vikingdb_service.async_get_collection("Ankur_Music_Collection")
    total_records = len(df)
    num_batches = math.ceil(total_records / batch_size)
    
    for i in range(num_batches):
        start_idx = i * batch_size
        end_idx = min((i + 1) * batch_size, total_records)
        batch_df = df[start_idx:end_idx]
        
        data_batch = []
        for _, row in batch_df.iterrows():
            field = {
                "artist": str(row['artist']),
                "song": str(row['song']),
                "vector": gen_random_vector(12),
                "duration_ms": int(row['duration_ms']),
                "explicit": bool(row['explicit']),
                "year": int(row['year']),
                "popularity": int(row['popularity']),
                "danceability": float(row['danceability']),
                "energy": float(row['energy']),
                "key": int(row['key']),
                "loudness": float(row['loudness']),
                "mode": int(row['mode']),
                "speechiness": float(row['speechiness']),
                "acousticness": float(row['acousticness']),
                "instrumentalness": float(row['instrumentalness']),
                "liveness": float(row['liveness']),
                "valence": float(row['valence']),
                "tempo": float(row['tempo']),
                "genre": str(row['genre'])
            }
            data_batch.append(Data(field))
        
        await collection.async_upsert_data(data_batch)
        print(f"Batch {i+1}/{num_batches} completed. Records {start_idx+1} to {end_idx} processed.")

async def main():
    # Read the CSV file
    df = pd.read_csv('/Users/bytedance/Documents/ByteDance/ModelArkDemo/VectorDB/songs_normalize.csv')
    await batch_upsert_data(df)
    print("All data has been uploaded successfully!")

if __name__ == "__main__":
    asyncio.run(main())