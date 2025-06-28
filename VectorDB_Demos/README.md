# image_search_app.py

## Overview
This application provides a user-friendly interface for searching e-Commerce fashion products using either text descriptions or image uploads. The application leverages VikingDB, a vector database service from BytePlus, to perform multimodal searches and find similar fashion products.

## Features
- Text-based Search : Users can enter text descriptions to find matching fashion products
- Image-based Search : Users can upload images to find visually similar fashion products
- Interactive UI : Clean interface with tabs for different search methods
- Detailed Results : Displays product information including name, color, and similarity score
## Technical Details
The application uses:

- Streamlit : For the web interface
- VikingDB : For vector similarity search
- BytePlus Object Storage (TOS) : For storing and retrieving product images
## How It Works
1. Text Search :
   
   - User enters a text description
   - The application converts this to a vector representation
   - VikingDB finds products with similar vector representations
   - Results are displayed with product details and images
2. Image Search :
   
   - User uploads an image
   - The image is encoded in base64 format
   - VikingDB finds visually similar products
   - Results are displayed with product details and images
3. Image Display :
   
   - Product images are stored in BytePlus Object Storage (TOS)
   - The application converts TOS paths to HTTP URLs for display
     
## Setup Requirements
- Python 3.6+
- Streamlit
- Pandas
- Pillow (PIL)
- BytePlus VikingDB SDK
