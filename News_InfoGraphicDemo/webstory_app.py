import os
import streamlit as st
import uuid
from datetime import datetime
from dotenv import load_dotenv

from webstory_generator import WebstoryGenerator
from webstory_storage import WebstoryStorage
from summarizer import ArticleSummarizer

# Load environment variables
load_dotenv()

# Add import at the top
from prompt_generator import PromptGenerator

# Load environment variables
load_dotenv()

# Add this function at the beginning of the file, after the imports

def track_token_usage(title, bullet_points):
    """Track token usage for the entire webstory generation process.
    
    Args:
        title (str): The webstory title.
        bullet_points (list): The bullet points for the webstory.
    """
    # Count total tokens for input content
    title_tokens = len(title.split())
    bullet_tokens = sum(len(point.split()) for point in bullet_points.strip().split("\n") if point.strip())
    total_input_tokens = title_tokens + bullet_tokens
    
    print("\n[TOKEN TRACKING] Webstory Generation Summary:")
    print(f"  - Title tokens (approx): {title_tokens}")
    print(f"  - Bullet points tokens (approx): {bullet_tokens}")
    print(f"  - Total input tokens (approx): {total_input_tokens}")
    
    # Fix: Store the result of the split operation in a variable first
    bullet_points_list = [p for p in bullet_points.strip().split("\n") if p.strip()]
    print(f"  - Number of images to generate: {1 + len(bullet_points_list)}")
    
    print("  Note: Detailed token usage for LLM and image generation is logged during processing.\n")

def generate_webstory_html(title, images):
    """Generate HTML for the webstory using AMP story format.
    
    Args:
        title (str): The title of the webstory.
        images (list): List of image data dictionaries.
        
    Returns:
        str: HTML content for the webstory.
    """
    html = f'''<!DOCTYPE html>
    <html amp lang="en">
    <head>
        <meta charset="utf-8">
        <script async src="https://cdn.ampproject.org/v0.js"></script>
        <title>{title}</title>
        <link rel="canonical" href="self.html">
        <meta name="viewport" content="width=device-width,minimum-scale=1,initial-scale=1">
        <script async custom-element="amp-story" src="https://cdn.ampproject.org/v0/amp-story-1.0.js"></script>
        <style amp-boilerplate>body{{-webkit-animation:-amp-start 8s steps(1,end) 0s 1 normal both;-moz-animation:-amp-start 8s steps(1,end) 0s 1 normal both;-ms-animation:-amp-start 8s steps(1,end) 0s 1 normal both;animation:-amp-start 8s steps(1,end) 0s 1 normal both}}@-webkit-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-moz-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-ms-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-o-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}</style><noscript><style amp-boilerplate>body{{-webkit-animation:none;-moz-animation:none;-ms-animation:none;animation:none}}</style></noscript>
        <style amp-custom>
            .story-card {{ padding: 20px; background: rgba(0,0,0,0.6); border-radius: 12px; }}
            h1, h2 {{ color: white; font-family: 'Montserrat', sans-serif; }}
            p {{ color: white; font-family: 'Montserrat', sans-serif; line-height: 1.4; }}
        </style>
    </head>
    <body>
        <amp-story standalone title="{title}">
'''

    # Add cover page
    html += f'''
            <amp-story-page id="cover">
                <amp-story-grid-layer template="fill">
                    <amp-img src="{images[0]['image_url']}" width="720" height="1280" layout="responsive"></amp-img>
                </amp-story-grid-layer>
                <amp-story-grid-layer template="vertical" class="text-center">
                    <div class="story-card">
                        <h1>{title}</h1>
                    </div>
                </amp-story-grid-layer>
            </amp-story-page>
    '''

    # Add story pages
    for i, img_data in enumerate(images[1:], 1):
        html += f'''
            <amp-story-page id="page{i}">
                <amp-story-grid-layer template="fill">
                    <amp-img src="{img_data['image_url']}" width="720" height="1280" layout="responsive"></amp-img>
                </amp-story-grid-layer>
                <amp-story-grid-layer template="vertical" class="text-center">
                    <div class="story-card">
                        <p>{img_data['text']}</p>
                    </div>
                </amp-story-grid-layer>
            </amp-story-page>
        '''

    # Close the story
    html += '''
        </amp-story>
    </body>
    </html>
    '''
    
    return html

# Initialize components
webstory_generator = WebstoryGenerator()
webstory_storage = WebstoryStorage()
summarizer = ArticleSummarizer()
prompt_generator = PromptGenerator()

# Set up the Streamlit page
st.set_page_config(page_title="News Webstory Generator", layout="wide")

# Instructions in the sidebar - MOVE THIS SECTION HERE
with st.sidebar:
    st.header("How to use")
    st.markdown(
        """1. Enter your article title and bullet points, or paste an existing article to generate summary points automatically."""
    )
    st.markdown(
        """2. Click 'Generate Webstory' to create your mobile-friendly webstory."""
    )
    st.markdown(
        """3. Use the preview to check your webstory slides."""
    )
    st.markdown(
        """4. Click the webstory link to view the full interactive version."""
    )
    
    st.header("About")
    st.markdown(
        """News Webstory Generator uses the following BytePlus technologies:"""
    )
    st.markdown(
        """- BytePlus text-to-image Vision model for generating webstory images"""
    )
    st.markdown(
        """- BytePlus Cloud Object Storage for storing webstories"""
    )

# App title and description
st.title("News Webstory Generator")
st.markdown(
    "Create mobile-friendly webstories from news articles. Enter your article title and bullet points below to generate a webstory!"
)

# Initialize session state
if "webstory_images" not in st.session_state:
    st.session_state.webstory_images = []

if "webstory_html_url" not in st.session_state:
    st.session_state.webstory_html_url = ""

if "current_image_index" not in st.session_state:
    st.session_state.current_image_index = 0

# Section 1: Article Summary Generation
st.header("1. Article Summary Generation")
col1, col2 = st.columns([1, 1])  # Adjust column widths to be equal

# In the article summary section
with col1:
    st.markdown("### Import from Existing Article")
    article_text = st.text_area(
        "Paste your article here to generate summary points",
        value="SAP Labs India's 41-acre campus at Devanahalli in Bengaluru will be ready by the second half of the year, generating a seating capacity of 15,000 more. SAP Labs India, which has been in operation since 1988, is home to 14,000 employees across five cities: Bengaluru, Gurugram, Mumbai, Hyderabad, and Pune. \n \n\"India is one of our largest development centres and our new facility, which will be opened later this year, will add to our capacity. From a product engineering perspective, given its size, the facility will be a self-sufficient and decoupled environment, said Mohammed Alam, Executive Board of SAP, and Head of the company's Product & Engineering. He was responding to a question on the impact of trade restrictions imposed by the US and visa restrictions, if any, on the company, at SAP Sapphire Orlando: 2025. \n \nSAP Labs Bangalore – the company's largest R&D hub outside Germany – is innovating key Artificial Intelligence use cases and drivers across the entire solution base - from S/4 HANA to HXM and the latest sustainability suite of solutions. One quarter of patents filed by SAP come from India, said a company official. \n \nThe company's CEO, Christian Klein, said its campuses in Palo Alto, Berlin has a lot of colleagues from India. Colleagues from the US work out of Bengaluru and other India locations. \"So far, we have not seen the impact of all the trade disruptions on business and IT,\" he said. \n \nThe company has not seen any delays in any of its IT projects. However, there could be disruptions in the supply chain, shift in manufacturing, change in logistics and enhanced delivery out of Indonesia, compared to China. \"This is where clients need technology more and we are super relevant these days,\" he said. \n \nPhilipp Herzig, Chief Technology Officer, SAP, earlier speaking to newspersons from APAC, said the main development team of Joule -- SAP's natural language generative AI co-pilot, designed to enhance user interaction with SAP business systems -- is actually coming out of India, together with the teams in Germany. \n \n\"The team in India is doing amazing things with Joule's core team building, the Joule framework technology. We have all lines of businesses in India,\" he said. \n \nTo actually make this huge progress, say to deliver 1,600 skills (check the stock level of material X in the warehouse is a skill), is the result of great collaboration that happened last year. \"We put all the developers in India, across all the various teams, in one room and made it happen _ we delivered across all lines of businesses. This amazing experience that we have today came out of SAP India Labs. \n \n\"Nearly 400 people in the India Labs worked on Joule, and continue to work on it. The number would be even more if you count the peoplecontributing indirectly as well, he said. \n \nManish Prasad, President and Managing Director for SAP Indian Subcontinent, said SAP India's growth story is in sync with that of SAP. \"India is now a strong and vibrant market for SAP. Business is growing across all verticals, including automobile, healthcare and retail. Indian companies are adopting AI at a really fast pace,\" he said. \"We are also tapping the tier-2 and tier-3 markets,\" he added. \n \nOn the greenfield facility coming up at Bengaluru, Prasad said the new centre, which is likely to be inaugurated in July-August, will have a Centre of Excellence, Concept Centres and a major focus on AI",
        height=200,
        key="article_text_input"
    )
    
    # Add the generate summary button
    if st.button("Generate Summary", key="generate_summary_btn"):
        if article_text.strip():
            with st.spinner("Generating summary..."):
                # Generate summary points using the summarizer
                title, summary_points = summarizer.summarize_article(article_text)
                # Update the bullet points text area and article title
                st.session_state.bullet_points = "\n".join(summary_points)
                st.session_state.article_title = title  # Add this line to store the title
                st.rerun()
        else:
            st.warning("Please paste an article first")

with col2:
    # Add vertical space before title input
    st.markdown("""<div style='padding-top: 60px;'>
    """, unsafe_allow_html=True)
    
    article_title = st.text_input(
        "Article Title", 
        key="article_title"
    )
    
    # Add vertical space before bullet points
    st.markdown("""<div style='padding-top: 20px;'>
    """, unsafe_allow_html=True)
    
    bullet_points = st.text_area(
        "Article Summary Bullet Points (one per line)",
        key="bullet_points"
    )

# Update webstory title value
#webstory_title = st.text_input(
 #   "Webstory Title", 
  #  value=st.session_state.get("article_title", article_title),
   # key="article_webstory_title"
#)

# Section 2: Webstory Creation
st.markdown("---")
st.header("2. Create Webstory")

webstory_title = st.text_input(
    "Webstory Title", 
    value=article_title, 
    key="final_webstory_title"
)
webstory_points = st.text_area(
    "Webstory Content Points (one per line)",
    value=bullet_points,
    height=200,
    key="webstory_points"
)

# Generate webstory button
if st.button("Generate Webstory", key="generate_webstory_btn"):
    try:
        with st.spinner("Generating webstory..."):
            # Clear previous images
            st.session_state.webstory_images = []
            
            # Generate enhanced title prompt and title image
            enhanced_title_prompt = prompt_generator.enhance_title_prompt(webstory_title)
            title_image_url = webstory_generator.generate_webstory_image(
                enhanced_title_prompt,
                style="title"
            )
            st.session_state.webstory_images.append({
                "image_url": title_image_url,
                "text": webstory_title
            })
            
            # Generate images for each bullet point
            for point in webstory_points.strip().split("\n"):
                if point.strip():
                    enhanced_bullet_prompt = prompt_generator.enhance_bullet_prompt(point)
                    image_url = webstory_generator.generate_webstory_image(enhanced_bullet_prompt)
                    st.session_state.webstory_images.append({
                        "image_url": image_url,
                        "text": point
                    })
            
            # Generate and save HTML content
            html_content = generate_webstory_html(webstory_title, st.session_state.webstory_images)
            st.session_state.webstory_html_url, st.session_state.webstory_download_url = webstory_storage.save_webstory(
                html_content,
                webstory_title
            )
            
            st.success("Webstory generated successfully!")
            
    except Exception as e:
        st.error(f"Error generating webstory: {str(e)}")

# Display generated webstory if available
if st.session_state.webstory_images:
    st.subheader("Preview Webstory")
    
    # Navigation buttons
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col1:
        if st.button("Previous") and st.session_state.current_image_index > 0:
            st.session_state.current_image_index -= 1
            st.rerun()
    
    with col3:
        if st.button("Next") and st.session_state.current_image_index < len(st.session_state.webstory_images) - 1:
            st.session_state.current_image_index += 1
            st.rerun()
    
    # Display current image
    current_image = st.session_state.webstory_images[st.session_state.current_image_index]
    st.image(
        current_image["image_url"],
        caption=current_image["text"],
        use_container_width=True  # Updated from use_column_width
    )
    
    # Display progress
    st.markdown(
        f"Page {st.session_state.current_image_index + 1} of {len(st.session_state.webstory_images)}"
    )
    
    # Display webstory link
    if st.session_state.webstory_html_url:
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"[🌐 View Full Webstory]({st.session_state.webstory_html_url})")
        with col2:
            st.markdown(f"[⬇️ Download HTML]({st.session_state.webstory_download_url})")