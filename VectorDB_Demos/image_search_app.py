import streamlit as st
import base64
from io import BytesIO
import pandas as pd
from PIL import Image
import os
import requests
import json
from volcengine.viking_db import *
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize VikingDB service
vikingdb_service = VikingDBService(os.getenv("VIKINGDB_ENDPOINT"), os.getenv("VIKINGDB_REGION"))
vikingdb_service.set_ak(os.getenv("VIKINGDB_AK"))
vikingdb_service.set_sk(os.getenv("VIKINGDB_SK"))

# Get the index (do this once during initialization)
index = vikingdb_service.get_index("Ankur_Product_Image_Collection", "Ankur_Product_Image_Index")

# BytePlus Skylark LLM API configuration
SKYLARK_API_URL = os.getenv("SKYLARK_API_URL")
SKYLARK_API_KEY = os.getenv("SKYLARK_API_KEY")
SKYLARK_MODEL = os.getenv("SKYLARK_MODEL")

def translate_to_english(text):
    """
    Translate non-English or mixed language text to English using Skylark LLM
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SKYLARK_API_KEY}"
    }
    
    payload = {
        "model": SKYLARK_MODEL,
        "messages": [
            {"role": "system", "content": "You are a language translator. Translate the given text to English. Only provide the translated text without any explanations or additional information."},
            {"role": "user", "content": text}
        ]
    }
    
    try:
        response = requests.post(SKYLARK_API_URL, headers=headers, json=payload)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        result = response.json()
        translated_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # Log the translation for debugging
        st.session_state.translation_log = f"Original: '{text}' → Translated: '{translated_text}'"
        
        return translated_text
    except Exception as e:
        st.error(f"Translation error: {str(e)}")
        return text  # Return original text if translation fails

def convert_tos_to_http_url(tos_path):
    """Convert TOS path to HTTP URL"""
    if not tos_path or not isinstance(tos_path, str):
        return None
    
    if tos_path.startswith('tos://'):
        # Extract the bucket and object key from the TOS path
        # Format: tos://{bucket}/{object_key}
        parts = tos_path.replace('tos://', '').split('/', 1)
        if len(parts) == 2:
            bucket = parts[0]
            object_key = parts[1]
            # Construct the HTTP URL
            return f"https://{bucket}.tos-ap-southeast-1.bytepluses.com/{object_key}"
    
    return tos_path  # Return original if not a TOS path or already HTTP

def search_with_text(text_query):
    """Search for similar images using text query"""
    try:
        # First, translate the query to English if it contains non-English text
        english_query = translate_to_english(text_query)
        
        # Use the translated query for search
        results = index.search_with_multi_modal(
            text=english_query,
            limit=10,  # Get top 10 similar images
            need_instruction=False,
            output_fields=["productDisplayName", "baseColour", "image"]
        )
        return results, english_query
    except Exception as e:
        st.error(f"Error searching with text: {str(e)}")
        return [], text_query

def search_with_image(image_file):
    """Search for similar images using uploaded image"""
    try:
        # Read the image file
        image_bytes = image_file.getvalue()
        
        # Convert to base64 for API
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Search using the image - add the required "base64://" prefix
        results = index.search_with_multi_modal(
            image=f"base64://{image_base64}",  # Add the required prefix
            limit=10,  # Get top 10 similar images
            need_instruction=False,
            output_fields=["productDisplayName", "baseColour", "image"]
        )
        return results
    except Exception as e:
        st.error(f"Error searching with image: {str(e)}")
        return []

def display_results(results):
    """Display search results in a grid layout with consistent alignment"""
    if not results:
        st.warning("No similar images found.")
        return
    
    # Create rows with 3 images each
    for i in range(0, len(results), 3):
        # Create a container for this row
        with st.container():
            cols = st.columns(3)
            
            # First pass: Display all images to ensure consistent alignment
            for j in range(3):
                if i + j < len(results):
                    result = results[i + j]
                    fields = result.fields
                    
                    with cols[j]:
                        # Display image first for consistent alignment
                        if 'image' in fields and fields['image']:
                            try:
                                # Convert TOS path to HTTP URL
                                image_url = convert_tos_to_http_url(fields['image'])
                                # Use use_container_width for consistent sizing
                                st.image(image_url, use_container_width=True)
                            except Exception as e:
                                st.error(f"Error displaying image: {str(e)}")
                                # Show placeholder for failed images
                                st.info("Image could not be displayed")
                        else:
                            st.info("No image available")
            
            # Second pass: Display all product information below images
            for j in range(3):
                if i + j < len(results):
                    result = results[i + j]
                    fields = result.fields
                    score = result.score
                    
                    with cols[j]:
                        # Display product information in a fixed-height container
                        with st.container():
                            st.markdown(f"**{fields.get('productDisplayName', 'Unknown Product')}**")
                            st.markdown(f"Color: {fields.get('baseColour', 'Unknown')}")
                            st.markdown(f"Similarity: {score:.2f}")
                        
                        # Add separator
                        st.markdown("---")

# Initialize session state for translation log
if 'translation_log' not in st.session_state:
    st.session_state.translation_log = ""

# Streamlit UI
st.title("Multimodal Search With BytePlus")
st.write("Image and multi-lingual semantic search for fashion e-Commerce store.")
st.write("Powered by BytePlus Skylark LLM and BytePlus VectorDB.")
# Create tabs for text search and image upload
tab1, tab2 = st.tabs(["Text Search", "Image Upload"])

with tab1:
    # Text search interface
    text_query = st.text_input("Enter search text (any language):")
    
    if text_query:
        with st.spinner('Searching for similar images...'):
            results, translated_query = search_with_text(text_query)
            
            # Show translation information if translation occurred
          #  if text_query != translated_query:
           #     st.info(f"Translated your query to: '{translated_query}'")
            
            display_results(results)

with tab2:
    # Image upload interface
    uploaded_file = st.file_uploader("Upload an image to find similar products:", type=["jpg", "jpeg", "png"])
    
    if uploaded_file:
        # Display the uploaded image
        # Use use_container_width instead of use_column_width
        st.image(uploaded_file, caption="Uploaded Image", width=300)
        
        # Search button
        if st.button("Search for Similar Images"):
            with st.spinner('Searching for similar images...'):
                results = search_with_image(uploaded_file)
                display_results(results)

# Add a collapsible section for debugging translation
with st.expander("Debug Information", expanded=False):
    st.write(st.session_state.translation_log)