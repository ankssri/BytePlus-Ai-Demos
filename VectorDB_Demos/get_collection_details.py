from volcengine.viking_db import *
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize service with .env credentials
vikingdb_endpoint = os.getenv("VIKINGDB_ENDPOINT", "api-vikingdb.mlp.ap-mya.byteplus.com")
vikingdb_region = os.getenv("VIKINGDB_REGION", "ap-southeast-1")
vikingdb_ak = os.getenv("VIKINGDB_AK")
vikingdb_sk = os.getenv("VIKINGDB_SK")

vikingdb_service = VikingDBService(vikingdb_endpoint, vikingdb_region)
vikingdb_service.set_ak(vikingdb_ak)
vikingdb_service.set_sk(vikingdb_sk)

def get_collection_sync():
    try:
        collection = vikingdb_service.get_collection("Ankur_NewsRAG_Collection")
        print(f"Collection Name: {collection.collection_name}")
        print(f"Fields: {[f.field_name for f in collection.fields]}")
        print(f"Indexes: {[i.index_name for i in collection.indexes]}")
        print(f"Stats: {collection.stat}")
    except Exception as e:
        print(f"Error: in get_collection_sync {str(e)}")

#async def get_collection_async():
#    try:
#        collection = await vikingdb_service.async_get_collection("Ankur_NewsRAG_Collection")
#        print(f"Async Collection Name: {collection.collection_name}")
#        print(f"Vector Fields: {[f for f in collection.fields if f.data_type == 'vector']}")
#    except Exception as e:
#        print(f"Async Error: in get_collection_async {str(e)}")

if __name__ == "__main__":
    get_collection_sync()
    #asyncio.run(get_collection_async())