import os
from byteplussdkarkruntime import Ark

# Make sure that you have stored the API Key in the environment variable ARK_API_KEY
# Initialize the Ark client to read your API Key from an environment variable
client = Ark(
    api_key="<your model ark api key from BytePlus console>",
    # Get your Key authentication from the environment variable. This is the default mode and you can modify it as required
    #api_key=os.environ.get("ARK_API_KEY"),
    # This is the default path. You can configure it based on the service location
    base_url="https://ark.ap-southeast.bytepluses.com/api/v3"
)
'''
# Non-streaming:
print("----- Non-streaming standard request -----")
completion = client.chat.completions.create(
   # Specify the Ark Inference Endpoint ID you created, which has been changed to your Inference Endpoint ID for you.
    model="ep-2025041xxxxxxk",
    messages=[
        {"role": "system", "content": "You are an artificial intelligence assistant."},
        {"role": "user", "content": "What are the common cruciferous plants?"}
    ],
)
print(completion.choices[0].message.content)'''

# Streaming:
print("------------------------------")
print("----- streaming request -----")
stream = client.chat.completions.create(
    model="<your modeal endpoint from BytePlus console e.g. ep-202504xxx >",
    messages=[
        {"role": "system", "content": "You are an ai assistant for ."},
        {"role": "user", "content": "Where is highest mountain in the world?"},
    ],
    # Whether the response content is streamed back
    stream=True,
)
for chunk in stream:
    if not chunk.choices:
        continue
    print(chunk.choices[0].delta.content, end="")
print()