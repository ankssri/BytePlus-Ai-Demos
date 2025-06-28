"""Main Streamlit application for News Article Summarizer and Infographic Generator."""

import os
import streamlit as st
from dotenv import load_dotenv

from summarizer import ArticleSummarizer
from image_generator import InfographicGenerator
from storage import StorageManager

# Load environment variables
load_dotenv()

# Initialize components
summarizer = ArticleSummarizer()
image_generator = InfographicGenerator()
storage_manager = StorageManager()

# Set up the Streamlit page
st.set_page_config(page_title="AiNewsHelper", layout="wide")

# App title and description
st.title("AiNewsHelper")
st.markdown(
    """This application helps you summarize news articles and generate infographic images. 
    Enter your article in the chat box below to get started!"""
)

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
user_input = st.chat_input("Enter your news article here...")

if user_input:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Process the article
    with st.spinner("Processing your article..."):
        try:
            # Extract a title from the first line or first sentence
            article_lines = user_input.strip().split('\n')
            article_title = article_lines[0] if article_lines else "News Article"
            
            # Generate summary
            article_title, summary_points = summarizer.summarize_article(user_input)
            
            # Remove this line as we now get title from summarizer
            # article_title = article_lines[0] if article_lines else "News Article"

            # Generate infographic
            infographic_url = image_generator.generate_infographic(article_title)
            
            # Save to storage
            image_storage_url = storage_manager.save_image(infographic_url, article_title)
            article_storage_url = storage_manager.save_article(user_input, article_title, summary_points)
            
            # Create response with card layout
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader(article_title)
                st.markdown("### Summary")
                for point in summary_points:
                    st.markdown(f"• {point}")
            
            with col2:
                st.subheader("Cover Image")
                st.image(infographic_url, caption=article_title, use_container_width=True)
                # Remove the download link from here
            
            # Add download links side by side below the summary section
            st.markdown("---")
            download_col1, download_col2 = st.columns(2)
            with download_col1:
                st.markdown(f"[📄 Download Article Summary]({article_storage_url})")
            with download_col2:
                st.markdown(f"[🖼️ Download Infographic]({image_storage_url})")
            
            # Add assistant response to chat history
            response_content = f"### {article_title}\n\n" + "\n\n".join([f"• {point}" for point in summary_points])
            response_content += f"\n\n---\n\n[📄 Download Article Summary]({article_storage_url}) | [🖼️ Download Infographic]({image_storage_url})"
            st.session_state.messages.append({"role": "assistant", "content": response_content})
            
        except Exception as e:
            error_message = f"Error processing your article: {str(e)}"
            st.error(error_message)
            st.session_state.messages.append({"role": "assistant", "content": error_message})

# Instructions in the sidebar
with st.sidebar:
    st.header("How to use")
    st.markdown(
        """1. Enter a news article in the chat box"""
    )
    st.markdown(
        """2. The AINewsHelper will generate a summary with up to 3 bullet points and cover images based on the article title"""
    )
    st.markdown(
        """3. Clik on artcile summary and image links to download"""
    )
    
    st.header("About")
    st.markdown(
        """AINewsHelper uses following BytePlus genAI technologies:"""
    )
    st.markdown(
        """- BytePlus LLM to summarize news articles"""
    )
    st.markdown(
        """- BytePlus text-to-image Vision model to generate contextual images based on article"""
    )
    st.markdown(
        """- BytePlus Cloud Object Storage to store and download generated images and summaries""")