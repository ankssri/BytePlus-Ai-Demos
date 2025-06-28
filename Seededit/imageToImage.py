import json
import sys
import os
import base64
import datetime
import hashlib
import hmac
import requests
import streamlit as st
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
        return None

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

# Streamlit UI
st.title("BytePlus Seededit Image Editor")

# Sidebar for API credentials
with st.sidebar:
    st.header("API Credentials")
    # Get credentials from environment variables or let user input them
    default_access_key = os.getenv('ACCESS_KEY', '')
    default_secret_key = os.getenv('SECRET_KEY', '')
    
    # Don't show the actual keys in the UI
    if default_access_key and default_secret_key:
        st.success("API credentials loaded from environment variables")
        use_env_credentials = st.checkbox("Use credentials from environment", value=True)
        if not use_env_credentials:
            access_key = st.text_input("Access Key", value="", type="password")
            secret_key = st.text_input("Secret Key", value="", type="password")
        else:
            access_key = default_access_key
            secret_key = default_secret_key
    else:
        use_env_credentials = False
        st.info("Your credentials are required to authenticate with the BytePlus API. You can set them in the .env file or enter them here.")
        access_key = st.text_input("Access Key", value="", type="password")
        secret_key = st.text_input("Secret Key", value="", type="password")

# Create tabs for different features
tab1, tab2 = st.tabs(["Image Editing", "Character Retention"])

# Tab 1: Original Image Editing functionality
with tab1:
    st.write("Upload an image and provide a prompt to edit it using BytePlus Seededit API")
    
    # Main content area
    uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"], key="image_edit_uploader")

    if uploaded_file is not None:
        # Display the uploaded image
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Image", use_container_width=True)
        
        # Get editing prompt from user
        prompt = st.text_input("Enter your editing prompt (e.g., 'Change to red clothes')", key="image_edit_prompt")
        
        # Advanced options with expander
        with st.expander("Advanced Options"):
            seed = st.number_input("Seed (-1 for random)", value=-1, key="image_edit_seed")
            scale = st.slider("Scale (influence of text description)", min_value=0.0, max_value=1.0, value=0.5, step=0.1, key="image_edit_scale")
            add_logo = st.checkbox("Add Watermark", value=False, key="image_edit_add_logo")
            
            # Logo options (only shown if add_logo is checked)
            if add_logo:
                logo_position = st.selectbox("Logo Position", options=["Bottom Right", "Bottom Left", "Top Right", "Top Left"], index=0, key="image_edit_logo_position")
                logo_language = st.selectbox("Logo Language", options=["English", "Chinese"], index=0, key="image_edit_logo_language")
                logo_text = st.text_input("Watermark Text", value="Generated with BytePlus Seededit", key="image_edit_logo_text")
                
                # Convert logo position to integer value
                position_map = {"Bottom Right": 0, "Bottom Left": 1, "Top Right": 2, "Top Left": 3}
                language_map = {"English": 0, "Chinese": 1}
                logo_position_value = position_map[logo_position]
                logo_language_value = language_map[logo_language]
            else:
                logo_position_value = 0
                logo_language_value = 0
                logo_text = ""
        
        # Process button
        if st.button("Generate Edited Image", key="generate_button_edit") and prompt:
            if not access_key or not secret_key:
                st.error("Please provide your API credentials in the sidebar or .env file")
            else:
                with st.spinner("Processing image..."):
                    # Prepare request
                    query_params = {
                        'Action': os.getenv('API_ACTION', 'CVProcess'),
                        'Version': os.getenv('API_VERSION', '2022-08-31'),
                    }
                    formatted_query = formatQuery(query_params)
                    
                    # Get image URL or use base64
                    image_url = upload_image_and_get_url(image)
                    
                    # Prepare request body
                    body_params = {
                        "req_key": os.getenv('REQ_KEY', 'byteedit_v2.0'),
                        "prompt": prompt,
                        "seed": seed,
                        "scale": scale,
                        "return_url": True,
                        "logo_info": {
                            "add_logo": add_logo,
                            "position": logo_position_value,
                            "language": logo_language_value,
                            "logo_text_content": logo_text
                        }
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
                            st.stop()  # Stop processing if validation fails
                    
                    formatted_body = json.dumps(body_params)
                    
                    # Make API request
                    status_code, response = signV4Request(access_key, secret_key, service,
                                                        formatted_query, formatted_body)
                    
                    if status_code == 200:
                        try:
                            response_json = json.loads(response)
                            if response_json.get("code") == 10000:
                                # Success
                                result_data = response_json.get("data", {})
                                
                                # Check if we have image URLs or base64 data
                                if result_data.get("image_urls") and len(result_data["image_urls"]) > 0:
                                    st.success("Image successfully edited!")
                                    
                                    # Clean the URL by removing any backticks or extra whitespace
                                    image_url = result_data["image_urls"][0]
                                    if isinstance(image_url, str):
                                        # More aggressive cleaning of the URL
                                        image_url = image_url.strip().strip('`').strip('"').strip()
                                    
                                    # Display the cleaned URL for debugging
                                    st.write("Image URL (for debugging):", image_url)
                                    
                                    # Try to display the image
                                    try:
                                        # Method 1: Direct Streamlit image display
                                        st.image(image_url, caption="Edited Image (Method 1)")
                                    except Exception as e:
                                        st.error(f"Error displaying image with method 1: {str(e)}")
                                    
                                    # Method 2: Alternative approach using HTML
                                    st.markdown(f"<img src='{image_url}' alt='Edited Image (Method 2)' style='width:100%'>\n\n[Download Image]({image_url})", unsafe_allow_html=True)
                                    
                                    # Method 3: Try downloading and displaying locally
                                    try:
                                        response = requests.get(image_url)
                                        if response.status_code == 200:
                                            img = Image.open(io.BytesIO(response.content))
                                            st.image(img, caption="Edited Image (Method 3 - Downloaded)")
                                        else:
                                            st.error(f"Failed to download image: HTTP {response.status_code}")
                                    except Exception as e:
                                        st.error(f"Error downloading image: {str(e)}")
                                    
                                    # Display additional information
                                    with st.expander("Response Details"):
                                        st.json(response_json)
                                elif result_data.get("binary_data_base64") and len(result_data["binary_data_base64"]) > 0:
                                    st.success("Image successfully edited!")
                                    img_data = base64.b64decode(result_data["binary_data_base64"][0])
                                    result_image = Image.open(io.BytesIO(img_data))
                                    st.image(result_image, caption="Edited Image")
                                    
                                    # Display additional information
                                    with st.expander("Response Details"):
                                        st.json(response_json)
                                else:
                                    st.error("No image data found in the response")
                            else:
                                st.error(f"API Error: {response_json.get('message', 'Unknown error')}")
                        except json.JSONDecodeError:
                            st.error("Failed to parse API response")
                            st.text(response)
                    else:
                        st.error(f"API request failed with status code: {status_code}")
        else:
            if not prompt and st.button("Generate Edited Image", key="generate_button_edit_warning"):
                st.warning("Please enter a prompt for editing the image")
    else:
        st.info("Please upload an image to get started")

# Tab 2: Character Retention functionality
with tab2:
    st.write("Upload an image and provide a prompt to generate a new image while preserving character appearance")
    st.info("This feature preserves subject appearance (humans, animals, objects) and facial features from the input image.")
    
    # Main content area for Character Retention
    uploaded_file_cr = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"], key="char_retention_uploader")

    if uploaded_file_cr is not None:
        # Display the uploaded image
        image_cr = Image.open(uploaded_file_cr)
        st.image(image_cr, caption="Uploaded Image", use_container_width=True)
        
        # Get prompt from user
        prompt_cr = st.text_input("Enter your prompt", key="char_retention_prompt")
        
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
            seed_cr = st.number_input("Seed (-1 for random)", value=-1, key="char_retention_seed")
            scale_cr = st.slider("Scale", min_value=1.0, max_value=10.0, value=3.5, step=0.5, help="Affects the degree of text description influence")
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
            add_logo_cr = st.checkbox("Add Watermark", value=False, key="char_retention_add_logo")
            
            # Logo options (only shown if add_logo is checked)
            if add_logo_cr:
                logo_position_cr = st.selectbox("Logo Position", options=["Bottom Right", "Bottom Left", "Top Right", "Top Left"], 
                                              index=0, key="char_retention_logo_position")
                logo_language_cr = st.selectbox("Logo Language", options=["English", "Chinese"], 
                                              index=0, key="char_retention_logo_language")
                logo_opacity_cr = st.slider("Logo Opacity", min_value=0.1, max_value=1.0, value=0.3, step=0.1)
                logo_text_cr = st.text_input("Watermark Text", value="Generated with BytePlus Character Retention", 
                                           key="char_retention_logo_text")
                
                # Convert logo position to integer value
                position_map = {"Bottom Right": 0, "Bottom Left": 1, "Top Right": 2, "Top Left": 3}
                language_map = {"English": 0, "Chinese": 1}
                logo_position_value_cr = position_map[logo_position_cr]
                logo_language_value_cr = language_map[logo_language_cr]
            else:
                logo_position_value_cr = 0
                logo_language_value_cr = 0
                logo_opacity_cr = 0.3
                logo_text_cr = ""
        
        # Process button for Character Retention
        generate_button_cr = st.button("Generate Image with Character Retention", key="generate_button_cr")
        if generate_button_cr:
            if not prompt_cr:
                st.warning("Please enter a prompt for character retention")
            elif not access_key or not secret_key:
                st.error("Please provide your API credentials in the sidebar or .env file")
            else:
                with st.spinner("Processing image..."):
                    # Prepare request
                    query_params = {
                        'Action': os.getenv('API_ACTION', 'CVProcess'),
                        'Version': os.getenv('API_VERSION', '2022-08-31'),
                    }
                    formatted_query = formatQuery(query_params)
                    
                    # Get image URL or use base64
                    image_url_cr = upload_image_and_get_url(image_cr)
                    
                    # Prepare request body for Character Retention
                    body_params_cr = {
                        "req_key": os.getenv('CHARACTER_RETENTION_REQ_KEY', 'high_aes_ip_v20'),  # Use env variable with fallback
                        "prompt": prompt_cr,
                        "desc_pushback": desc_pushback,
                        "seed": seed_cr,
                        "scale": scale_cr,
                        "ddim_steps": ddim_steps,
                        "width": width,
                        "height": height,
                        "cfg_rescale": cfg_rescale,
                        "ref_ip_weight": ref_ip_weight,
                        "ref_id_weight": ref_id_weight,
                        "use_sr": use_sr,
                        "return_url": True,
                        "logo_info": {
                            "add_logo": add_logo_cr,
                            "position": logo_position_value_cr,
                            "language": logo_language_value_cr,
                            "opacity": logo_opacity_cr,
                            "logo_text_content": logo_text_cr
                        }
                    }
                    
                    # Add either image_urls or binary_data_base64 based on what's available
                    if image_url_cr:
                        body_params_cr["image_urls"] = [image_url_cr]
                    else:
                        # Use base64 encoding
                        try:
                            img_base64_cr = encode_image(image_cr)
                            body_params_cr["binary_data_base64"] = [img_base64_cr]
                        except ValueError as e:
                            st.error(f"Image validation error: {str(e)}")
                            st.stop()  # Stop processing if validation fails
                    
                    formatted_body_cr = json.dumps(body_params_cr)
                    
                    # Make API request
                    status_code_cr, response_cr = signV4Request(access_key, secret_key, service,
                                                             formatted_query, formatted_body_cr)
                    
                    if status_code_cr == 200:
                        try:
                            response_json_cr = json.loads(response_cr)
                            if response_json_cr.get("code") == 10000:
                                # Success
                                result_data_cr = response_json_cr.get("data", {})
                                
                                # Check if we have image URLs or base64 data
                                if result_data_cr.get("image_urls") and len(result_data_cr["image_urls"]) > 0:
                                    st.success("Image successfully generated with character retention!")
                                    
                                    # Clean the URL by removing any backticks or extra whitespace
                                    image_url_result = result_data_cr["image_urls"][0]
                                    if isinstance(image_url_result, str):
                                        # More aggressive cleaning of the URL
                                        image_url_result = image_url_result.strip().strip('`').strip('"').strip()
                                    
                                    # Display the cleaned URL for debugging
                                    st.write("Image URL (for debugging):", image_url_result)
                                    
                                    # Try to display the image
                                    try:
                                        # Method 1: Direct Streamlit image display
                                        st.image(image_url_result, caption="Generated Image with Character Retention (Method 1)")
                                    except Exception as e:
                                        st.error(f"Error displaying image with method 1: {str(e)}")
                                    
                                    # Method 2: Alternative approach using HTML
                                    st.markdown(f"<img src='{image_url_result}' alt='Generated Image (Method 2)' style='width:100%'>\n\n[Download Image]({image_url_result})", unsafe_allow_html=True)
                                    
                                    # Method 3: Try downloading and displaying locally
                                    try:
                                        response = requests.get(image_url_result)
                                        if response.status_code == 200:
                                            img = Image.open(io.BytesIO(response.content))
                                            st.image(img, caption="Generated Image (Method 3 - Downloaded)")
                                        else:
                                            st.error(f"Failed to download image: HTTP {response.status_code}")
                                    except Exception as e:
                                        st.error(f"Error downloading image: {str(e)}")
                                    
                                    # Display additional information
                                    with st.expander("Response Details"):
                                        st.json(response_json_cr)
                                elif result_data_cr.get("binary_data_base64") and len(result_data_cr["binary_data_base64"]) > 0:
                                    st.success("Image successfully generated with character retention!")
                                    img_data_cr = base64.b64decode(result_data_cr["binary_data_base64"][0])
                                    result_image_cr = Image.open(io.BytesIO(img_data_cr))
                                    st.image(result_image_cr, caption="Generated Image with Character Retention")
                                    
                                    # Display additional information
                                    with st.expander("Response Details"):
                                        st.json(response_json_cr)
                                else:
                                    st.error("No image data found in the response")
                            else:
                                st.error(f"API Error: {response_json_cr.get('message', 'Unknown error')}")
                        except json.JSONDecodeError:
                            st.error("Failed to parse API response")
                            st.text(response_cr)
                    else:
                        st.error(f"API request failed with status code: {status_code_cr}")
        # Remove the else block with the duplicate button
    else:
        st.info("Please upload an image to get started")

# Footer
st.markdown("---")
st.caption("BytePlus Seededit Image Editor - Powered by BytePlus Visual API")