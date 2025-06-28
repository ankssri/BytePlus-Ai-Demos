from volcengine.viking_db import *
import asyncio

vikingdb_service = VikingDBService("api-vikingdb.mlp.ap-mya.byteplus.com", "ap-southeast-1")
vikingdb_service.set_ak("<BytePlus API Key>")
vikingdb_service.set_sk("<BytePlus Secret Key>")


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
asyncio.run(get_collection())