import os
import time
import statistics
from byteplussdkarkruntime import Ark
client = Ark(api_key="<your api key>")
def run_latency_test():
    # Recording start time
    start_time = time.time()
    first_token_time = None
    full_response = ""
    completion = client.chat.completions.create(
        model="<your model id name from BytePlus console e.g. ep-2025xxxx>",
        messages=[
                {"role": "system", "content": "You are Skylark, an AI assistant developed by BytePlus"},
                {"role": "user", "content": "What is the highest mountain in the world?"},
        ],
        stream=True
    )
    for chunk in completion:
        if first_token_time is None:
            first_token_time = time.time()
        if chunk.choices[0].delta.content:
            full_response += chunk.choices[0].delta.content
    end_time = time.time()
    ttft = (first_token_time - start_time) * 1000
    total_latency = (end_time - start_time) * 1000
    return ttft, total_latency, full_response
# Run 20 tests
num_tests = 20
ttft_results = []
latency_results = []
print(f"----- Running {num_tests} latency tests -----\n")
for i in range(num_tests):
    print(f"Test {i + 1}/{num_tests}")
    ttft, latency, response = run_latency_test()
    ttft_results.append(ttft)
    latency_results.append(latency)
    print(f"TTFT: {ttft:.2f}ms")
    print(f"Total Latency: {latency:.2f}ms")
    print(f"Response: {response}\n")
    # Add a short delay between tests to avoid too frequent requests
    time.sleep(1)
# Calculate the mean and standard deviation
avg_ttft = statistics.mean(ttft_results)
avg_latency = statistics.mean(latency_results)
std_ttft = statistics.stdev(ttft_results)
std_latency = statistics.stdev(latency_results)
print("\n----- Summary Statistics -----")
print(f"Average TTFT: {avg_ttft:.2f}ms (±{std_ttft:.2f}ms)")
print(f"Average Total Latency: {avg_latency:.2f}ms (±{std_latency:.2f}ms)")
# Print minimum and maximum values
print(f"\nTTFT Range: {min(ttft_results):.2f}ms - {max(ttft_results):.2f}ms")
print(f"Total Latency Range: {min(latency_results):.2f}ms - {max(latency_results):.2f}ms")