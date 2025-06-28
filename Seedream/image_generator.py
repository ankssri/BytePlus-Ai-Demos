"""Streamlit application for BytePlus image generation."""

import os
import json
import requests
import streamlit as st
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO

# Load environment variables
load_dotenv()

# Set up the Streamlit page
st.set_page_config(page_title="Seedream 3.0", layout="wide")

# App title and description
st.title("Seedream 3.0 BytePlus Image Generator")
st.markdown(
    """BytePlus image generation AI model. 
    Enter your prompt in the text box below to get started!"""
)

# API configuration
API_ENDPOINT = "https://ark.ap-southeast.bytepluses.com/api/v3/images/generations"
API_KEY = os.getenv("ARK_API_KEY")

# Default parameters
DEFAULT_MODEL = os.getenv("IMAGE_MODEL", "ep-20250606195130-bmvt2")
DEFAULT_SIZE = "1024x1024"
DEFAULT_GUIDANCE_SCALE = 3
model = DEFAULT_MODEL
# Sidebar for advanced options
st.sidebar.title("Advanced Options")
#model = st.sidebar.text_input("Model ID", DEFAULT_MODEL)
size = st.sidebar.selectbox("Image Size", ["256x256", "512x512", "1024x1024"], index=2)
guidance_scale = st.sidebar.slider("Guidance Scale", 1, 10, DEFAULT_GUIDANCE_SCALE)
watermark = st.sidebar.checkbox("Add Watermark", value=True)

# Main input area
# Initialize session state for prompt text if not exists
if 'prompt_text' not in st.session_state:
    st.session_state.prompt_text = ""

# Function to set prompt text when copy button is clicked
def set_prompt_text(prompt_text):
    st.session_state.prompt_text = prompt_text

prompt = st.text_area("Enter your prompt here or copy prompts given below", 
                     value=st.session_state.prompt_text,
                     height=100)

# Generate button
if st.button("Generate Image"):
    if not prompt:
        st.error("Please enter a prompt to generate an image.")
    elif not API_KEY:
        st.error("API key not found. Please set the ARK_API_KEY environment variable.")
    else:
        with st.spinner("Generating image..."): 
            # Prepare request payload
            payload = {
                "model": model,
                "prompt": prompt,
                "response_format": "url",
                "size": size,
                "guidance_scale": guidance_scale,
                "watermark": watermark
            }
            
            # Set headers
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}"
            }
            
            try:
                # Make API request
                response = requests.post(
                    API_ENDPOINT,
                    headers=headers,
                    json=payload
                )
                
                # Check for successful response
                if response.status_code == 200:
                    result = response.json()
                    
                    # Display the generated image
                    if "data" in result and len(result["data"]) > 0 and "url" in result["data"][0]:
                        image_url = result["data"][0]["url"]
                        st.success("Image generated successfully!")
                        
                        # Display image
                        st.image(image_url, caption="Generated Image", use_container_width=True)
                        
                        # Display image URL
                        st.markdown(f"**Image URL:** {image_url}")
                        
                        # Display API response details
                        with st.expander("API Response Details"):
                            st.json(result)
                    else:
                        st.error("No image URL found in the API response.")
                        st.json(result)
                else:
                    st.error(f"API request failed with status code {response.status_code}")
                    st.text(response.text)
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")

# Sample Prompts
st.markdown("---")
st.markdown("### Sample Prompts")

# Define sample prompts
sample_prompts = [
    "Anime With Text: Anime Friendly looking male who is wearing a black anti-hero mask, a black combat suit and headphones. He is sitting behind his laptop in his office, arms on his desk, eyes are glowing bright. It is night. The room has volumetric lighting. He is front facing to the camera, looking straight and centered, central portrait, sitting straight, front view, centered looking straight. Word bubble to display text \"I will be back\"",
    "Comic : A heroic space captain with a retro silver spacesuit firing a ray gun at alien invaders, with a backdrop of exploding planets and swirling galaxies. Dramatic retro comic fonts like \"ZAP!\" and \"BLAST!\" — style: vintage sci-fi comic, halftone textures, bold lines, saturated primary colors, retro-futuristic design.",
    "Fashion Clothing: Studio style photorealistic poster of a male model wearing high quality cotton white t-shirt.  Subtle fabric movement creating natural folds. Studio lighting emphasizing garment construction. Clean composition with strategic shadows. Professional product photography",
    "Fashion Jewellery : A hyperrealistic, high-jewelry advertisement-style photograph of a sophisticated, elegant woman with a long, graceful neck wearing an intricate gold necklace. The model has flawless skin and her hair is styled in a sophisticated updo. She is wearing a simple, off-the-shoulder black velvet gown. The necklace is crafted from gleaming 22k yellow gold in an elegant bib design. It features multiple cascading pendants shaped like stylized, open flower buds. Each pendant is exquisitely set with a combination of faceted gemstones: translucent rose quartz, deep pink rubies, and brilliant green tsavorites. The delicate chain is adorned with small, embossed star details. The image is a macro shot, showcasing the fine craftsmanship and texture of the jewelry. The lighting is soft and diffused, creating a luxurious, ethereal glow on a seamless, light grey background.",
    "Product Display : Minimalist product display photo of a blue color perfume bottle with floating geometric shapes, soft glowing lights, white and gold color palette, clean and elegant design, high-resolution. perfume bottle to stand out when compared to background",
    "Product Display : A stunning studio photograph of an opulent, handcrafted necklace from a luxury collection. The design is inspired by a blossoming garden, with a draping bib silhouette made of warm, polished yellow gold. It features a cascade of intricate, dangling charms that resemble stylized lotus buds and tulips. These charms are adorned with a carefully arranged palette of precious stones: soft, glowing rose quartz cabochons, sparkling pink sapphires, and vivid Colombian emeralds. The design is symmetrical and intricate. The image is captured in ultra-high resolution (8K), with professional studio lighting that highlights the gleam of the gold and the inner fire of the gems, set against a sophisticated, muted backdrop.",
    "Landscape : A photorealistic poster of a birds-eye view of a remote, tropical island paradise in the sun with pristine, white sand beaches. Showcase  breathtaking sunset, and island's rugged coastline, coral reefs, and the vast, shimmering expanse of the surrounding ocean."
]

# Display each prompt with a copy button
for i, prompt_text in enumerate(sample_prompts):
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"{i+1}. {prompt_text}")
    with col2:
        st.button(f"Copy", key=f"copy_btn_{i}", on_click=set_prompt_text, args=(prompt_text,))

# Display API information
st.markdown("---")
st.markdown("### API Information")
st.markdown(f"**Endpoint:** {API_ENDPOINT}")
st.markdown(f"**Model:** {model}")