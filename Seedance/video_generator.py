"""Streamlit application for BytePlus video generation."""

import os
import json
import time
import requests
import streamlit as st
from dotenv import load_dotenv
import base64
from io import BytesIO
from PIL import Image
import re

# Load environment variables
load_dotenv()

# Set up the Streamlit page
st.set_page_config(page_title="Seedance 1.0", layout="wide")

# App title and description
st.title("Seedance 1.0 BytePlus Video Generator")
st.markdown(
    """BytePlus's text-to-video and image-to video generation AI model. 
    Enter your prompt in the text box below to get started!"""
)

# API configuration
CREATE_TASK_ENDPOINT = "https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks"
QUERY_TASK_ENDPOINT = "https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks/"
API_KEY = os.getenv("ARK_API_KEY")
# Add debug print to verify API key is available (remove in production)
if not API_KEY:
    print("Warning: ARK_API_KEY environment variable is not set")

# Default parameters
TEXT_TO_VIDEO_MODEL = os.getenv("TEXT_TO_VIDEO_MODEL", "ep-20250609151607-f8djs")
IMAGE_TO_VIDEO_MODEL = os.getenv("IMAGE_TO_VIDEO_MODEL", "ep-20250609155925-vfg9s")
DEFAULT_MODEL = TEXT_TO_VIDEO_MODEL

# Image URLs for dropdown
IMAGE_URLS = {
    "None": None,
    "Anime": "https://ankurdemo.tos-ap-southeast-1.bytepluses.com/newsArticle/Anime.jpeg",
    "Fashion Clothing": "https://ankurdemo.tos-ap-southeast-1.bytepluses.com/newsArticle/fashion.jpeg",
    "Fashion eCommerce": "https://ankurdemo.tos-ap-southeast-1.bytepluses.com/newsArticle/whitetshirt.jpeg",
    "Fashion Jewellery": "https://ankurdemo.tos-ap-southeast-1.bytepluses.com/newsArticle/model.jpeg",
    "Product Display" : "https://ankurdemo.tos-ap-southeast-1.bytepluses.com/newsArticle/perfume%20bottle.jpeg",
    "Flower" : "https://ankurdemo.tos-ap-southeast-1.bytepluses.com/newsArticle/Flower.jpeg",
    "Landscape" : "https://ankurdemo.tos-ap-southeast-1.bytepluses.com/newsArticle/landscape_island.jpeg"
}

# Helper function to validate image
def validate_image(image):
    # Check image format
    valid_formats = ['JPEG', 'JPG', 'PNG', 'WEBP', 'BMP', 'TIFF', 'GIF']
    if image.format not in valid_formats:
        return False, f"Invalid image format. Supported formats: {', '.join(valid_formats)}"
    
    # Check aspect ratio
    width, height = image.size
    aspect_ratio = width / height
    if not (0.4 <= aspect_ratio <= 2.5):
        return False, f"Invalid aspect ratio: {aspect_ratio:.2f}. Must be between 0.4 and 2.5"
    
    # Check pixel dimensions
    if width < 300 or height < 300:
        return False, f"Image dimensions too small: {width}x{height}. Short side must be at least 300px"
    if width > 6000 or height > 6000:
        return False, f"Image dimensions too large: {width}x{height}. Long side must be less than 6000px"
    
    return True, "Image is valid"

# Helper function to convert image to base64
def image_to_base64(image, format="JPEG"):
    # Convert image to RGB mode if it has an alpha channel
    if image.mode == 'RGBA':
        # Create a white background
        background = Image.new('RGB', image.size, (255, 255, 255))
        # Paste the image using alpha channel as mask
        background.paste(image, mask=image.split()[3])
        image = background
    elif image.mode != 'RGB':
        image = image.convert('RGB')
        
    # Standardize format to uppercase
    format = format.upper()
    if format == 'JPG':
        format = 'JPEG'
        
    # Resize image if it's too large (optional)
    max_dimension = 2048  # Reasonable size for API
    width, height = image.size
    if width > max_dimension or height > max_dimension:
        if width > height:
            new_width = max_dimension
            new_height = int(height * (max_dimension / width))
        else:
            new_height = max_dimension
            new_width = int(width * (max_dimension / height))
        image = image.resize((new_width, new_height), Image.LANCZOS)
    
    # Convert to base64
    buffered = BytesIO()
    image.save(buffered, format=format, quality=90)  # Adjust quality for JPEG
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/{format.lower()};base64,{img_str}"

# Sidebar for sample prompts
st.sidebar.title("Sample Prompts")

# Sample prompts with copy buttons
sample_prompts = [
    "Aerial shot: slow-motion shot, wide-angle camera slowly crosses the Amazon River, and the rainforest on both sides of the river is clearly visible. --ratio 16:9 --resolution 1080p --duration 5",
    "A photorealistic, sun-drenched video. A 5-year-old girl with curly blonde hair, wearing a simple white sundress, has a beaming, joyful smile on her face. She is gently holding a fluffy, playful Golden Retriever puppy in her arms. She walks at a relaxed pace through lush, green rolling hills dotted with yellow wildflowers. The camera follows alongside her in a smooth tracking shot. The sky is a brilliant, clear blue.",
    "Handheld camera, the picture slightly shakes to reflect the handheld feeling, following a cat walking in the rose garden"
]

# Function to set prompt text when copy button is clicked
def set_prompt_text(prompt_text):
    st.session_state.prompt_text = prompt_text

# Initialize session state for prompt text if not exists
if 'prompt_text' not in st.session_state:
    st.session_state.prompt_text = ""

# Display each prompt with a copy button
for i, prompt_text in enumerate(sample_prompts):
    col1, col2 = st.sidebar.columns([4, 1])
    with col1:
        st.write(f"{i+1}. {prompt_text}")
    with col2:
        st.button(f"Copy", key=f"copy_btn_{i}", on_click=set_prompt_text, args=(prompt_text,))

#text_to_video_model = st.sidebar.text_input("Text-to-Image", TEXT_TO_VIDEO_MODEL)
#image_to_video_model = st.sidebar.text_input("Image-to-Video Model ID", IMAGE_TO_VIDEO_MODEL)
text_to_video_model = TEXT_TO_VIDEO_MODEL
image_to_video_model = IMAGE_TO_VIDEO_MODEL

# Helper function to create video generation task
def create_video_task(prompt, model_id, image_url=None, uploaded_image_base64=None):
    # Prepare content list for the request payload
    content = []
    
    # Add text prompt if provided
    if prompt:
        content.append({
            "type": "text",
            "text": prompt
        })
    
    # Add image URL if provided from dropdown
    if image_url:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": image_url
            }
        })
    # Add base64 encoded image if uploaded
    elif uploaded_image_base64:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": uploaded_image_base64
            }
        })
    
    # Prepare request payload
    payload = {
        "model": model_id,
        "content": content
    }
    
    # Set headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    # Debug payload size
    payload_size = len(json.dumps(payload))
    print(f"Payload size: {payload_size} bytes")
    
    # Make API request
    try:
        response = requests.post(
            CREATE_TASK_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=30  # Add timeout
        )
        
        # Add debugging for error cases
        if response.status_code != 200:
            try:
                error_detail = response.json()
                print(f"API Error: {error_detail}")
                # Return error details for UI display
                return None, error_detail
            except:
                error_text = response.text
                print(f"API Error: {error_text}")
                return None, {"error": error_text}
        
        # Check for successful response
        if response.status_code == 200:
            result = response.json()
            if "id" in result:
                return result["id"], None
        
        # Fallback error
        return None, {"error": f"Unexpected response: {response.status_code}"}
    
    except Exception as e:
        print(f"Request exception: {str(e)}")
        return None, {"error": str(e)}

# Helper function to check video generation task status
def check_video_task(task_id):
    # Set headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    # Make API request
    response = requests.get(
        f"{QUERY_TASK_ENDPOINT}{task_id}",
        headers=headers
    )
    
    # Check for successful response
    if response.status_code == 200:
        return response.json()
    
    # Raise exception if task query failed
    response.raise_for_status()
    return None

# Main input area
prompt = st.text_area("Enter your prompt here", 
                     value=st.session_state.prompt_text,
                     height=150,
                     placeholder="Describe the video you want to generate. You can include style, scene, camera movement, etc. Example: Photorealistic style: Under a clear blue sky, a vast expanse of white daisy fields stretches out. --ratio 16:9 --resolution 720p --duration 5")

# Create tabs for image selection methods
image_tab1, image_tab2 = st.tabs(["Select from Library", "Upload Image"])

# Tab 1: Image selection dropdown
with image_tab1:
    selected_image = st.selectbox(
        "Select an image for image-to-video generation",
        list(IMAGE_URLS.keys()),
        index=0
    )
    # Get the selected image URL
    selected_image_url = IMAGE_URLS[selected_image]
    
    # Display selected image if any
    if selected_image_url:
        st.image(selected_image_url, caption=f"Selected image: {selected_image}", width=400)

# Tab 2: Image upload
with image_tab2:
    st.markdown("""### Upload an image from your device""")
    uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png", "webp", "bmp", "tiff", "gif"])
    
    # Initialize variables for uploaded image
    uploaded_image = None
    uploaded_image_base64 = None
    
    if uploaded_file is not None:
        try:
            # Read the image
            image = Image.open(uploaded_file)
            
            # Validate the image
            is_valid, message = validate_image(image)
            
            if is_valid:
                # Convert to base64
                uploaded_image_base64 = image_to_base64(image, format=image.format)
                uploaded_image = image
                
                # Display the uploaded image
                st.image(image, caption="Uploaded image", width=400)
                st.success(message)
                
                # Display image details
                width, height = image.size
                st.info(f"Image details: {width}x{height} pixels, Format: {image.format}, Aspect ratio: {width/height:.2f}")
            else:
                st.error(message)
        except Exception as e:
            st.error(f"Error processing image: {str(e)}")

# Generate button
if st.button("Generate Video"):
    # Determine which image source to use
    using_uploaded_image = uploaded_image_base64 is not None
    using_library_image = selected_image_url is not None and not using_uploaded_image
    
    if not prompt and not using_uploaded_image and not using_library_image:
        st.error("Please enter a prompt or select/upload an image to generate a video.")
    elif not API_KEY:
        st.error("API key not found. Please set the ARK_API_KEY environment variable.")
    else:
        # Create a placeholder for the status message
        status_placeholder = st.empty()
        
        try:
            # Step 1: Create video generation task
            status_placeholder.info("Creating video generation task...")
            
            # Select the appropriate model based on whether an image is provided
            selected_model = image_to_video_model if (using_uploaded_image or using_library_image) else text_to_video_model
            
            # Debug information
            with st.expander("Debug Info (Expand to see request details)"):
                st.write(f"Using model: {selected_model}")
                st.write(f"Text prompt: {prompt if prompt else 'None'}")
                if using_library_image:
                    st.write(f"Image URL: {selected_image_url}")
                elif using_uploaded_image:
                    st.write("Using uploaded image (base64 encoded)")
                    # Show image format and size
                    if uploaded_image:
                        width, height = uploaded_image.size
                        st.write(f"Image dimensions: {width}x{height}")
                        st.write(f"Image format: {uploaded_image.format}")
                else:
                    st.write("No image selected")

            # Create the task with the appropriate image source
            image_url_to_use = selected_image_url if using_library_image else None
            task_id, error_details = create_video_task(prompt, selected_model, image_url_to_use, uploaded_image_base64)
            
            if not task_id:
                st.error("Failed to create video generation task.")
                if error_details:
                    with st.expander("Error Details"):
                        st.json(error_details)
            else:
                # Continue with existing task polling code...
                st.success(f"Video generation task created successfully! Task ID: {task_id}")
                
                # Step 2: Poll for task completion
                progress_bar = st.progress(0)
                status_placeholder.info("Processing video generation task... This may take several minutes.")
                
                # Initialize variables for polling
                max_attempts = 60  # Maximum number of polling attempts
                poll_interval = 10  # Seconds between polling attempts
                attempts = 0
                task_completed = False
                
                while attempts < max_attempts and not task_completed:
                    # Update progress bar
                    progress = min(0.95, attempts / max_attempts)
                    progress_bar.progress(progress)
                    
                    # Check task status
                    task_result = check_video_task(task_id)
                    
                    if task_result and "status" in task_result:
                        status = task_result["status"]
                        status_placeholder.info(f"Task status: {status}. Please wait...")
                        
                        if status.lower() == "succeeded":
                            task_completed = True
                            progress_bar.progress(1.0)
                            
                            # Extract video URL
                            if "content" in task_result and "video_url" in task_result["content"]:
                                video_url = task_result["content"]["video_url"]
                                
                                # Display success message
                                status_placeholder.success("Video generated successfully!")
                                
                                # Display video
                                st.video(video_url)
                                
                                # Display video URL
                                st.markdown(f"**Video URL:** {video_url}")
                                
                                # Display API response details
                                with st.expander("API Response Details"):
                                    st.json(task_result)
                                    
                                # Clear the prompt text after successful generation
                                st.session_state.prompt_text = ""
                            else:
                                st.error("No video URL found in the API response.")
                                st.json(task_result)
                        elif status.lower() in ["failed", "error"]:
                            st.error(f"Video generation task failed: {task_result.get('error', 'Unknown error')}")
                            break
                    
                    # Wait before next polling attempt if task not completed
                    if not task_completed:
                        time.sleep(poll_interval)
                        attempts += 1
                
                # Check if maximum attempts reached
                if attempts >= max_attempts and not task_completed:
                    status_placeholder.warning("Maximum polling time reached. The video may still be processing.")
                    st.markdown(f"You can manually check the status later using task ID: **{task_id}**")
        
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            # Add more detailed error information
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                try:
                    error_detail = json.loads(e.response.text)
                    st.error(f"API Error Details: {error_detail}")
                except:
                    st.error(f"API Response: {e.response.text}")

# Display usage instructions
st.markdown("---")
st.markdown("### Usage Instructions")
st.markdown("""
1. Enter your text prompt in the text area above (optional if using an image)
2. Select an image from the dropdown for image-to-video generation (optional if using text prompt)
3. Adjust the model ID in the sidebar if needed
4. Click the 'Generate Video' button
5. Wait for the video to be generated and displayed (this may take several minutes)

**Prompt Tips:**
- Include style descriptions (e.g., photorealistic, cartoon, anime)
- Describe the scene, subjects, and actions
- Add camera movement instructions if desired
- Use parameters like `--ratio 16:9`, `--resolution 720p`, `--duration 5` to customize the output
""")

# Display API information
st.markdown("---")
st.markdown("### API Information")
st.markdown(f"**Create Task Endpoint:** {CREATE_TASK_ENDPOINT}")
st.markdown(f"**Query Task Endpoint:** {QUERY_TASK_ENDPOINT}[task_id]")
#st.markdown(f"**Text-to-Video Model:** {text_to_video_model}")
#st.markdown(f"**Image-to-Video Model:** {image_to_video_model}")