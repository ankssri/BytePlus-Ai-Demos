import streamlit as st
import requests
import json
import time

# API Configuration
API_BASE_URL = "https://hiagent-byteplus.volcenginepaas.com/api/proxy/api/v1"
API_KEY = "<my app api key>"
APP_ID = "<my app id>"
USER_ID = "123"

# Headers for API requests
HEADERS = {
    "Apikey": API_KEY,
    "Content-Type": "application/json"
}

# Set page title and configure layout
st.set_page_config(page_title="AI Agent Chat", layout="wide")
st.title("BytePlus AI Agent Chat")

# Initialize session state for chat history if it doesn't exist
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Function to call the run_app_workflow API
def run_app_workflow(question):
    url = f"{API_BASE_URL}/run_app_workflow"
    payload = {
        "UserID": USER_ID,
        "AppID": APP_ID,
        "InputData": json.dumps({"question": question})
    }
    
    try:
        response = requests.post(url, headers=HEADERS, json=payload)
        response.raise_for_status()
        return response.json().get("runId")
    except requests.exceptions.RequestException as e:
        st.error(f"Error calling run_app_workflow API: {str(e)}")
        return None

# Function to call the query_run_app_process API
def query_run_app_process(run_id):
    url = f"{API_BASE_URL}/query_run_app_process"
    payload = {
        "UserID": USER_ID,
        "AppID": APP_ID,
        "RunID": run_id
    }
    
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            response = requests.post(url, headers=HEADERS, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # Check if processing is complete
            if data.get("status") == "success":
                # Find the end node to get the final output
                for node_id, node_data in data.get("nodes", {}).items():
                    if node_data.get("nodeType") == "end":
                        try:
                            # Parse the output JSON string
                            output_data = json.loads(node_data.get("output", "{}"))
                            return output_data.get("output", "No response from AI agent")
                        except json.JSONDecodeError:
                            return "Error parsing AI agent response"
            
            # If not complete, wait and retry
            time.sleep(2)
            retry_count += 1
        except requests.exceptions.RequestException as e:
            st.error(f"Error calling query_run_app_process API: {str(e)}")
            return f"Error: {str(e)}"
    
    return "Timeout: AI agent did not respond in time"

# Extract and format the AI response
def extract_ai_response(response_text):
    # Clean up the response if needed
    return response_text

# Chat input
if prompt := st.chat_input("Ask a question about shipping, returns, etc."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Display assistant response with a spinner while waiting
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            # Step 1: Call run_app_workflow to get run_id
            run_id = run_app_workflow(prompt)
            
            if run_id:
                # Step 2: Call query_run_app_process to get the response
                response_text = query_run_app_process(run_id)
                
                # Step 3: Format and display the response
                formatted_response = extract_ai_response(response_text)
                st.markdown(formatted_response)
                
                # Add assistant response to chat history
                st.session_state.messages.append({"role": "assistant", "content": formatted_response})
            else:
                st.error("Failed to get a response from the AI agent")