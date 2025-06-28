import json
import sys
import os
import base64
import datetime
import hashlib
import hmac
import requests
import streamlit as st
import time
from PIL import Image
import io
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Configuration from environment variables
method = 'POST'
host = os.getenv('API_HOST', 'visual.volcengineapi.com')
region = os.getenv('API_REGION', 'cn-north-1')
endpoint = os.getenv('API_ENDPOINT', 'https://visual.volcengineapi.com')
service = os.getenv('API_SERVICE', 'cv')

# Signing functions
def sign(key, msg):
    return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

def getSignatureKey(key, dateStamp, regionName, serviceName):
    kDate = sign(key.encode('utf-8'), dateStamp)
    kRegion = sign(kDate, regionName)
    kService = sign(kRegion, serviceName)
    kSigning = sign(kService, 'request')
    return kSigning

def formatQuery(parameters):
    request_parameters_init = ''
    for key in sorted(parameters):
        request_parameters_init += key + '=' + parameters[key] + '&'
    request_parameters = request_parameters_init[:-1]
    return request_parameters

def signV4Request(access_key, secret_key, service, req_query, req_body):
    if access_key is None or secret_key is None:
        st.error('No access key is available.')
        return None, None

    t = datetime.datetime.utcnow()
    current_date = t.strftime('%Y%m%dT%H%M%SZ')
    datestamp = t.strftime('%Y%m%d')  # Date w/o time, used in credential scope
    canonical_uri = '/'
    canonical_querystring = req_query
    signed_headers = 'content-type;host;x-content-sha256;x-date'
    payload_hash = hashlib.sha256(req_body.encode('utf-8')).hexdigest()
    content_type = 'application/json'
    canonical_headers = 'content-type:' + content_type + '\n' + 'host:' + host + \
        '\n' + 'x-content-sha256:' + payload_hash + \
        '\n' + 'x-date:' + current_date + '\n'
    canonical_request = method + '\n' + canonical_uri + '\n' + canonical_querystring + \
        '\n' + canonical_headers + '\n' + signed_headers + '\n' + payload_hash
    
    algorithm = 'HMAC-SHA256'
    credential_scope = datestamp + '/' + region + '/' + service + '/' + 'request'
    string_to_sign = algorithm + '\n' + current_date + '\n' + credential_scope + '\n' + hashlib.sha256(
        canonical_request.encode('utf-8')).hexdigest()
    
    signing_key = getSignatureKey(secret_key, datestamp, region, service)
    signature = hmac.new(signing_key, (string_to_sign).encode(
        'utf-8'), hashlib.sha256).hexdigest()

    authorization_header = algorithm + ' ' + 'Credential=' + access_key + '/' + \
        credential_scope + ', ' + 'SignedHeaders=' + \
        signed_headers + ', ' + 'Signature=' + signature
    
    headers = {'X-Date': current_date,
               'Authorization': authorization_header,
               'X-Content-Sha256': payload_hash,
               'Content-Type': content_type
               }

    # Send the request
    request_url = endpoint + '?' + canonical_querystring

    try:
        r = requests.post(request_url, headers=headers, data=req_body)
        # Use the replace method to replace \u0026 with &
        resp_str = r.text.replace("\\u0026", "&")
        return r.status_code, resp_str
    except Exception as err:
        st.error(f'Error occurred: {err}')
        return None, None

# Function to encode image to base64
def encode_image(image):
    # Check image dimensions and ratio
    width, height = image.size
    max_dimension = max(width, height)
    min_dimension = min(width, height)
    aspect_ratio = max_dimension / min_dimension
    
    # Check if aspect ratio exceeds API requirements
    if aspect_ratio > 3:
        raise ValueError(f"Image aspect ratio ({aspect_ratio:.2f}) exceeds the maximum allowed ratio of 3.0")
    
    # Check if image dimensions exceed maximum allowed
    if width > 4096 or height > 4096:
        raise ValueError(f"Image dimensions ({width}x{height}) exceed the maximum allowed size of 4096x4096")
    
    # Convert RGBA to RGB if needed
    if image.mode == 'RGBA':
        # Create a white background image
        background = Image.new('RGB', image.size, (255, 255, 255))
        # Paste the image on the background
        background.paste(image, mask=image.split()[3])  # 3 is the alpha channel
        image = background
    
    # Save as JPEG with quality setting to control file size
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG", quality=95)
    
    # Check file size
    file_size = buffered.getbuffer().nbytes
    max_size = 4.7 * 1024 * 1024  # 4.7 MB in bytes
    
    # If file size exceeds limit, reduce quality until it fits
    if file_size > max_size:
        quality = 90
        while file_size > max_size and quality >= 70:
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG", quality=quality)
            file_size = buffered.getbuffer().nbytes
            quality -= 5
        
        if file_size > max_size:
            # If still too large, resize the image
            scale_factor = 0.9
            while file_size > max_size and scale_factor >= 0.5:
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                resized_img = image.resize((new_width, new_height), Image.LANCZOS)
                
                buffered = io.BytesIO()
                resized_img.save(buffered, format="JPEG", quality=85)
                file_size = buffered.getbuffer().nbytes
                scale_factor -= 0.1
            
            if file_size > max_size:
                raise ValueError(f"Unable to reduce image size below the maximum allowed size of 4.7 MB")
    
    # Get base64 string
    buffered.seek(0)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return img_str

# Function to upload image to a temporary server and get URL
# Note: In a real application, you would need to implement this
# For this example, we'll use base64 encoding instead
def upload_image_and_get_url(image):
    # This is a placeholder - in a real app, you would upload the image to a server
    # and return the URL. For this example, we'll return None to use base64 instead.
    return None

# Function to submit a task to the seededit v3.0 API
def submit_task_v3(access_key, secret_key, image, prompt, seed, scale, add_logo=False, logo_position=0, logo_language=0, logo_text=""):
    # Prepare request
    query_params = {
        'Action': 'CVSync2AsyncSubmitTask',
        'Version': '2022-08-31',
    }
    formatted_query = formatQuery(query_params)
    
    # Get image URL or use base64
    image_url = upload_image_and_get_url(image)
    
    # Prepare request body
    body_params = {
        "req_key": "seededit_v3.0",
        "prompt": prompt,
        "seed": seed,
        "scale": scale
    }
    
    # Add either image_urls or binary_data_base64 based on what's available
    if image_url:
        body_params["image_urls"] = [image_url]
    else:
        # Use base64 encoding
        try:
            img_base64 = encode_image(image)
            body_params["binary_data_base64"] = [img_base64]
        except ValueError as e:
            st.error(f"Image validation error: {str(e)}")
            return None
    
    # Add logo info if needed
    if add_logo:
        logo_info = {
            "add_logo": add_logo,
            "position": logo_position,
            "language": logo_language,
            "logo_text_content": logo_text
        }
        # Convert to JSON string for req_json parameter
        req_json = json.dumps({"logo_info": logo_info, "return_url": True})
        body_params["req_json"] = req_json
    else:
        # Always set return_url to true
        req_json = json.dumps({"return_url": True})
        body_params["req_json"] = req_json
    
    formatted_body = json.dumps(body_params)
    
    # Make API request
    status_code, response = signV4Request(access_key, secret_key, service,
                                        formatted_query, formatted_body)
    
    if status_code == 200:
        try:
            response_json = json.loads(response)
            if response_json.get("code") == 10000:
                # Success - return task_id
                return response_json.get("data", {}).get("task_id")
            else:
                st.error(f"API Error: {response_json.get('message', 'Unknown error')}")
                return None
        except json.JSONDecodeError:
            st.error("Failed to parse API response")
            st.text(response)
            return None
    else:
        st.error(f"API request failed with status code: {status_code}")
        return None

# Function to query task status and get result for seededit v3.0
def query_task_v3(access_key, secret_key, task_id, add_logo=False, logo_position=0, logo_language=0, logo_opacity=0.3, logo_text=""):
    # Prepare request
    query_params = {
        'Action': 'CVSync2AsyncGetResult',
        'Version': '2022-08-31',
    }
    formatted_query = formatQuery(query_params)
    
    # Prepare request body
    body_params = {
        "req_key": "seededit_v3.0",
        "task_id": task_id
    }
    
    # Add logo info if needed
    if add_logo:
        logo_info = {
            "add_logo": add_logo,
            "position": logo_position,
            "language": logo_language,
            "opacity": logo_opacity,
            "logo_text_content": logo_text
        }
        # Convert to JSON string for req_json parameter
        req_json = json.dumps({"logo_info": logo_info, "return_url": True})
        body_params["req_json"] = req_json
    else:
        # Always set return_url to true
        req_json = json.dumps({"return_url": True})
        body_params["req_json"] = req_json
    
    formatted_body = json.dumps(body_params)
    
    # Make API request
    status_code, response = signV4Request(access_key, secret_key, service,
                                        formatted_query, formatted_body)
    
    if status_code == 200:
        try:
            response_json = json.loads(response)
            if response_json.get("code") == 10000:
                # Success - return data
                return response_json.get("data", {}), response_json.get("data", {}).get("status")
            else:
                st.error(f"API Error: {response_json.get('message', 'Unknown error')}")
                return None, None
        except json.JSONDecodeError:
            st.error("Failed to parse API response")
            st.text(response)
            return None, None
    else:
        st.error(f"API request failed with status code: {status_code}")
        return None, None

# Function to process image with seededit v2.0 (Character Retention)
def process_image_v2(access_key, secret_key, image, prompt, params):
    # Prepare request
    query_params = {
        'Action': 'CVProcess',
        'Version': '2022-08-31',
    }
    formatted_query = formatQuery(query_params)
    
    # Get image URL or use base64
    image_url = upload_image_and_get_url(image)
    
    # Prepare request body
    body_params = {
        "req_key": "high_aes_ip_v20",  # Character Retention API key
        "prompt": prompt,
        "return_url": True,
        **params  # Include all other parameters
    }
    
    # Add either image_urls or binary_data_base64 based on what's available
    if image_url:
        body_params["image_urls"] = [image_url]
    else:
        # Use base64 encoding
        try:
            img_base64 = encode_image(image)
            body_params["binary_data_base64"] = [img_base64]
        except ValueError as e:
            st.error(f"Image validation error: {str(e)}")
            return None, None
    
    formatted_body = json.dumps(body_params)
    
    # Make API request
    status_code, response = signV4Request(access_key, secret_key, service,
                                        formatted_query, formatted_body)
    
    if status_code == 200:
        try:
            response_json = json.loads(response)
            if response_json.get("code") == 10000:
                # Success
                return response_json.get("data", {}), True
            else:
                st.error(f"API Error: {response_json.get('message', 'Unknown error')}")
                return None, False
        except json.JSONDecodeError:
            st.error("Failed to parse API response")
            st.text(response)
            return None, False
    else:
        st.error(f"API request failed with status code: {status_code}")
        return None, False

# Streamlit UI
st.set_page_config(page_title="BytePlus Seededit", layout="wide")

# Sidebar for API credentials
with st.sidebar:
    st.title("API Credentials")
    st.info("Enter your trial api key and secrect key")
    
    # Seededit v3.0 credentials
    st.header("Image Editing Credentials")
    # Get credentials from environment variables
    default_access_key_v3 = os.getenv('ACCESS_KEY', '')
    default_secret_key_v3 = os.getenv('SECRET_KEY', '')
    
    # Don't show the actual keys in the UI
    if default_access_key_v3 and default_secret_key_v3:
        st.success("Seededit credentials loaded from environment variables")
        use_env_credentials_v3 = st.checkbox("Use default credentials from environment", value=True, key="use_env_v3")
        if not use_env_credentials_v3:
            access_key_v3 = st.text_input("Access Key", value="", type="password", key="access_key_v3")
            secret_key_v3 = st.text_input("Secret Key", value="", type="password", key="secret_key_v3")
        else:
            access_key_v3 = default_access_key_v3
            secret_key_v3 = default_secret_key_v3
    else:
        use_env_credentials_v3 = False
        st.info("Your Seededit api key and secret key are required for image editing model.")
        access_key_v3 = st.text_input("Access Key", value="", type="password", key="access_key_v3")
        secret_key_v3 = st.text_input("Secret Key", value="", type="password", key="secret_key_v3")
    
    # Seededit v2.0 credentials
    st.header("Character Retention Credentials")
    # Get credentials from environment variables
    default_access_key_v2 = os.getenv('ACCESS_KEY_V2', default_access_key_v3)  # Fallback to v3 if not specified
    default_secret_key_v2 = os.getenv('SECRET_KEY_V2', default_secret_key_v3)  # Fallback to v3 if not specified
    
    # Option to use same credentials as v3.0
    use_same_credentials = st.checkbox("Use same credentials as Image Editor model", value=True, key="use_same_creds")
    
    if use_same_credentials:
        access_key_v2 = access_key_v3
        secret_key_v2 = secret_key_v3
    else:
        # Don't show the actual keys in the UI
        if default_access_key_v2 and default_secret_key_v2 and default_access_key_v2 != default_access_key_v3:
            st.success("Character retention model credentials loaded from environment variables")
            use_env_credentials_v2 = st.checkbox("Use v2.0 credentials from environment", value=True, key="use_env_v2")
            if not use_env_credentials_v2:
                access_key_v2 = st.text_input("Seededit v2.0 Access Key", value="", type="password", key="access_key_v2")
                secret_key_v2 = st.text_input("Seededit v2.0 Secret Key", value="", type="password", key="secret_key_v2")
            else:
                access_key_v2 = default_access_key_v2
                secret_key_v2 = default_secret_key_v2
        else:
            use_env_credentials_v2 = False
            st.info("Your character retention model credentials are required.")
            access_key_v2 = st.text_input("Character Retention Access Key", value="", type="password", key="access_key_v2")
            secret_key_v2 = st.text_input("Character Retention Secret Key", value="", type="password", key="secret_key_v2")

# Main content area
st.title("BytePlus Seededit")

# Create tabs for different features
tab1, tab2 = st.tabs(["Image Editing", "Character Retention"])

# Tab 1: Image Editing with Seededit v3.0
with tab1:
    st.write("Upload an image and provide a prompt to edit it using BytePlus Seededit API")
    
    # Image uploader
    uploaded_file_v3 = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"], key="image_edit_uploader_v3")

    if uploaded_file_v3 is not None:
        # Display the uploaded image
        image_v3 = Image.open(uploaded_file_v3)
        # Reduce preview size by setting a specific width instead of using container width
        st.image(image_v3, caption="Uploaded Image", width=400)
        
        # Get editing prompt from user
        prompt_v3 = st.text_input("Enter your editing prompt (e.g., 'Change to red clothes')", key="prompt_v3")
        
        # Advanced options with expander
        with st.expander("Advanced Options"):
            seed_v3 = st.number_input("Seed (-1 for random)", value=-1, key="seed_v3")
            scale_v3 = st.slider("Scale (influence of text description)", min_value=0.0, max_value=1.0, value=0.5, step=0.1, key="scale_v3")
            add_logo_v3 = st.checkbox("Add Watermark", value=False, key="add_logo_v3")
            
            # Logo options (only shown if add_logo is checked)
            if add_logo_v3:
                logo_position_v3 = st.selectbox("Logo Position", options=["Bottom Right", "Bottom Left", "Top Right", "Top Left"], index=0, key="logo_position_v3")
                logo_language_v3 = st.selectbox("Logo Language", options=["English", "Chinese"], index=0, key="logo_language_v3")
                logo_opacity_v3 = st.slider("Logo Opacity", min_value=0.1, max_value=1.0, value=0.3, step=0.1, key="logo_opacity_v3")
                logo_text_v3 = st.text_input("Watermark Text", value="Generated with BytePlus Seededit v3.0", key="logo_text_v3")
                
                # Convert logo position to integer value
                position_map = {"Bottom Right": 0, "Bottom Left": 1, "Top Right": 2, "Top Left": 3}
                language_map = {"English": 0, "Chinese": 1}
                logo_position_value_v3 = position_map[logo_position_v3]
                logo_language_value_v3 = language_map[logo_language_v3]
            else:
                logo_position_value_v3 = 0
                logo_language_value_v3 = 0
                logo_opacity_v3 = 0.3
                logo_text_v3 = ""
        
        # Process button
        if st.button("Generate Edited Image", key="generate_button_v3"):
            if not prompt_v3:
                st.warning("Please enter a prompt for editing the image")
            elif not access_key_v3 or not secret_key_v3:
                st.error("Please provide your Seededit v3.0 API credentials in the sidebar")
            else:
                # Step 1: Submit the task
                with st.spinner("Submitting image editing task..."):
                    task_id = submit_task_v3(
                        access_key_v3, 
                        secret_key_v3, 
                        image_v3, 
                        prompt_v3, 
                        seed_v3, 
                        scale_v3, 
                        add_logo_v3, 
                        logo_position_value_v3, 
                        logo_language_value_v3, 
                        logo_text_v3
                    )
                    
                    if task_id:
                        st.success(f"Task submitted successfully! Task ID: {task_id}")
                        
                        # Create a placeholder for the progress bar and status message
                        progress_placeholder = st.empty()
                        status_placeholder = st.empty()
                        
                        # Step 2: Poll for results
                        max_attempts = 30  # Maximum number of polling attempts
                        polling_interval = 2  # Time between polling attempts in seconds
                        
                        for attempt in range(max_attempts):
                            # Update progress bar
                            progress = min(0.1 + (attempt / max_attempts) * 0.9, 0.95)  # Start at 10%, cap at 95%
                            progress_placeholder.progress(progress)
                            
                            # Update status message
                            status_placeholder.info(f"Checking task status... (Attempt {attempt + 1}/{max_attempts})")
                            
                            # Query task status
                            result_data, status = query_task_v3(
                                access_key_v3, 
                                secret_key_v3, 
                                task_id,
                                add_logo_v3,
                                logo_position_value_v3,
                                logo_language_value_v3,
                                logo_opacity_v3,
                                logo_text_v3
                            )
                            
                            if status == "done":
                                # Task completed successfully
                                progress_placeholder.progress(1.0)  # Complete the progress bar
                                status_placeholder.success("Image editing completed!")
                                
                                # Display the result
                                if result_data.get("image_urls") and len(result_data["image_urls"]) > 0:
                                    # Clean the URL by removing any backticks or extra whitespace
                                    image_url = result_data["image_urls"][0]
                                    if isinstance(image_url, str):
                                        # More aggressive cleaning of the URL
                                        image_url = image_url.strip().strip('`').strip('"').strip()
                                        
                                        # Follow redirects to get final URL
                                        try:
                                            response = requests.head(image_url, allow_redirects=True)
                                            if response.status_code == 200:
                                                image_url = response.url
                                        except Exception as e:
                                            st.warning(f"Could not follow URL redirects: {str(e)}")
                                    
                                    # Try to display the image - use only one method
                                    try:
                                        # Method 1: Direct Streamlit image display
                                        st.image(image_url, caption="Edited Image", width=400)
                                        
                                        # Add download link separately
                                        st.markdown(f"[Download Edited Image]({image_url})")
                                    except Exception as e:
                                        st.error(f"Error displaying image: {str(e)}")
                                        # Only use Method 2 if Method 1 fails
                                        st.markdown(f"<img src='{image_url}' alt='Edited Image' style='width:100%'>\n\n[Download Image]({image_url})", unsafe_allow_html=True)
                                    
                                    # Display additional information
                                    with st.expander("Response Details"):
                                        st.json(result_data)
                                elif result_data.get("binary_data_base64") and len(result_data["binary_data_base64"]) > 0:
                                    st.success("Image successfully edited!")
                                    img_data = base64.b64decode(result_data["binary_data_base64"][0])
                                    result_image = Image.open(io.BytesIO(img_data))
                                    st.image(result_image, caption="Edited Image", use_container_width=True)
                                    
                                    # Display additional information
                                    with st.expander("Response Details"):
                                        st.json(result_data)
                                else:
                                    st.error("No image data found in the response")
                                
                                break
                            elif status == "generating":
                                # Task is still processing
                                status_placeholder.info("Task is being processed...")
                            elif status == "in_queue":
                                # Task is in queue
                                status_placeholder.info("Task is in queue...")
                            elif status == "not_found" or status == "expired":
                                # Task not found or expired
                                progress_placeholder.empty()
                                status_placeholder.error(f"Task {status}. Please try again.")
                                break
                            else:
                                # Unknown status
                                status_placeholder.warning(f"Unknown task status: {status}")
                            
                            # Wait before next polling attempt
                            time.sleep(polling_interval)
                        
                        # Check if we've reached maximum attempts
                        if attempt >= max_attempts - 1 and status != "done":
                            progress_placeholder.empty()
                            status_placeholder.error("Maximum polling attempts reached. The task may still be processing. Please try again later.")
                    else:
                        st.error("Failed to submit task. Please check your inputs and try again.")
        # Remove this second button completely - don't even leave it commented
    else:
        st.info("Please upload an image to get started")

# Tab 2: Character Retention with Seededit v2.0
with tab2:
    st.write("Upload an image and provide a prompt to generate a new image while preserving character appearance")
    st.info("This feature preserves subject appearance (humans, animals, objects) and facial features from the input image.")
    
    # Main content area for Character Retention
    uploaded_file_v2 = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"], key="char_retention_uploader")

    if uploaded_file_v2 is not None:
        # Display the uploaded image
        image_v2 = Image.open(uploaded_file_v2)
        # Reduce preview size by setting a specific width instead of using container width
        st.image(image_v2, caption="Uploaded Image", width=400)
        
        # Get prompt from user
        prompt_v2 = st.text_input("Enter your prompt", key="char_retention_prompt")
        
        # Advanced options with expander
        with st.expander("Advanced Options"):
            # Character Retention specific options
            use_sr = st.checkbox("Use Super-Resolution", value=True, help="Enhances image quality with AIGC super-resolution")
            desc_pushback = st.checkbox("Description Pushback", value=True, help="Conducts reverse inference based on input image content for more stable results")
            
            # Image dimensions
            col1, col2 = st.columns(2)
            with col1:
                width = st.number_input("Width", min_value=256, max_value=768, value=512, step=64, help="Width of generated image before super-resolution")
            with col2:
                height = st.number_input("Height", min_value=256, max_value=768, value=512, step=64, help="Height of generated image before super-resolution")
            
            # Generation parameters
            seed_v2 = st.number_input("Seed (-1 for random)", value=-1, key="char_retention_seed")
            scale_v2 = st.slider("Scale", min_value=1.0, max_value=10.0, value=3.5, step=0.5, help="Affects the degree of text description influence")
            ddim_steps = st.slider("DDIM Steps", min_value=1, max_value=50, value=9, step=1, help="Steps for generating the image")
            cfg_rescale = st.slider("CFG Rescale", min_value=0.0, max_value=1.0, value=0.7, step=0.1)
            
            # Subject appearance and facial features weights
            col3, col4 = st.columns(2)
            with col3:
                ref_ip_weight = st.slider("Subject Appearance Weight", min_value=0.0, max_value=1.0, value=0.7, step=0.05, 
                                         help="Weight of subject appearance in reference image. Higher values increase similarity.")
            with col4:
                ref_id_weight = st.slider("Facial Features Weight", min_value=0.0, max_value=1.0, value=0.36, step=0.02, 
                                         help="Weight of facial features in reference image. Recommended range: 0.2-0.4")
            
            # Watermark options
            add_logo_v2 = st.checkbox("Add Watermark", value=False, key="char_retention_add_logo")
            
            # Logo options (only shown if add_logo is checked)
            if add_logo_v2:
                logo_position_v2 = st.selectbox("Logo Position", options=["Bottom Right", "Bottom Left", "Top Right", "Top Left"], 
                                              index=0, key="char_retention_logo_position")
                logo_language_v2 = st.selectbox("Logo Language", options=["English", "Chinese"], 
                                              index=0, key="char_retention_logo_language")
                logo_opacity_v2 = st.slider("Logo Opacity", min_value=0.1, max_value=1.0, value=0.3, step=0.1, key="logo_opacity_v2")
                logo_text_v2 = st.text_input("Watermark Text", value="Generated with BytePlus Character Retention", 
                                           key="char_retention_logo_text")
                
                # Convert logo position to integer value
                position_map = {"Bottom Right": 0, "Bottom Left": 1, "Top Right": 2, "Top Left": 3}
                language_map = {"English": 0, "Chinese": 1}
                logo_position_value_v2 = position_map[logo_position_v2]
                logo_language_value_v2 = language_map[logo_language_v2]
            else:
                logo_position_value_v2 = 0
                logo_language_value_v2 = 0
                logo_opacity_v2 = 0.3
                logo_text_v2 = ""
        
        # Process button for Character Retention - ensure there's only one button
        generate_button_v2 = st.button("Generate Image with Character Retention", key="generate_button_v2")
        if generate_button_v2:
            if not prompt_v2:
                st.warning("Please enter a prompt for character retention")
            elif not access_key_v2 or not secret_key_v2:
                st.error("Please provide your Seededit v2.0 API credentials in the sidebar")
            else:
                with st.spinner("Processing image..."):
                    # Prepare additional parameters
                    params = {
                        "desc_pushback": desc_pushback,
                        "seed": seed_v2,
                        "scale": scale_v2,
                        "ddim_steps": ddim_steps,
                        "width": width,
                        "height": height,
                        "cfg_rescale": cfg_rescale,
                        "ref_ip_weight": ref_ip_weight,
                        "ref_id_weight": ref_id_weight,
                        "use_sr": use_sr,
                        "logo_info": {
                            "add_logo": add_logo_v2,
                            "position": logo_position_value_v2,
                            "language": logo_language_value_v2,
                            "opacity": logo_opacity_v2,
                            "logo_text_content": logo_text_v2
                        }
                    }
                    
                    # Process the image
                    result_data_v2, success = process_image_v2(access_key_v2, secret_key_v2, image_v2, prompt_v2, params)
                    
                    if success and result_data_v2:
                        st.success("Image successfully generated with character retention!")
                        
                        # Check if we have image URLs or base64 data
                        if result_data_v2.get("image_urls") and len(result_data_v2["image_urls"]) > 0:
                            # Clean the URL by removing any backticks or extra whitespace
                            image_url_result = result_data_v2["image_urls"][0]
                            if isinstance(image_url_result, str):
                                # More aggressive cleaning of the URL
                                image_url_result = image_url_result.strip().strip('`').strip('"').strip()
                                
                                # Follow redirects to get final URL
                                try:
                                    response = requests.head(image_url_result, allow_redirects=True)
                                    if response.status_code == 200:
                                        image_url_result = response.url
                                except Exception as e:
                                    st.warning(f"Could not follow URL redirects: {str(e)}")
                            
                            # Try to display the image
                            try:
                                # Direct Streamlit image display
                                st.image(image_url_result, caption="Generated Image with Character Retention", width=400)
                                
                                # Add download link separately
                                st.markdown(f"[Download Generated Image]({image_url_result})")
                            except Exception as e:
                                st.error(f"Error displaying image: {str(e)}")
                                # Alternative approach using HTML
                                st.markdown(f"<img src='{image_url_result}' alt='Generated Image' style='width:100%'>\n\n[Download Image]({image_url_result})", unsafe_allow_html=True)
                            
                            # Display additional information
                            with st.expander("Response Details"):
                                st.json(result_data_v2)
                        elif result_data_v2.get("binary_data_base64") and len(result_data_v2["binary_data_base64"]) > 0:
                            img_data_v2 = base64.b64decode(result_data_v2["binary_data_base64"][0])
                            result_image_v2 = Image.open(io.BytesIO(img_data_v2))
                            st.image(result_image_v2, caption="Generated Image with Character Retention", width=400)
                            
                            # Display additional information
                            with st.expander("Response Details"):
                                st.json(result_data_v2)
                        else:
                            st.error("No image data found in the response")
                    else:
                        st.error("Failed to generate image. Please check your inputs and try again.")
    else:
        st.info("Please upload an image to get started")

# Footer
st.markdown("---")
st.caption("Powered by BytePlus Seededit Model")