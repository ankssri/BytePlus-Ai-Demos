from volcengine.viking_db import *
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get API credentials from environment variables
vikingdb_endpoint = os.getenv("VIKINGDB_ENDPOINT", "api-vikingdb.mlp.ap-mya.byteplus.com")
vikingdb_region = os.getenv("VIKINGDB_REGION", "ap-southeast-1")
vikingdb_ak = os.getenv("VIKINGDB_AK")
vikingdb_sk = os.getenv("VIKINGDB_SK")

# Initialize VikingDB service with environment variables
vikingdb_service = VikingDBService(vikingdb_endpoint, vikingdb_region)
vikingdb_service.set_ak(vikingdb_ak)
vikingdb_service.set_sk(vikingdb_sk)


# collection = vikingdb_service.get_collection("Ankur_Music_Collection")

#res = collection.fetch_data("22")

#async def fetch_data():
#    collection = vikingdb_service.get_collection("Ankur_Music_Collection")
#    res = await collection.async_fetch_data(["2687576463354582338", "7807251929453703333"])
#    for item in res: 
#        print(item) 
#        print(item.fields) 
#asyncio.run(fetch_data())




async def get_collection():
    #
    res = await vikingdb_service.async_get_collection("Ankur_NewsRAG_Collection")
    #print(res)
    for item in res: 
        print(item) 
        print(item.fields)

if __name__ == "__main__":
    asyncio.run(get_collection())