import streamlit as st
from volcengine.viking_db import *
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize VikingDB service
vikingdb_service = VikingDBService(os.getenv("VIKINGDB_ENDPOINT"), os.getenv("VIKINGDB_REGION"))
vikingdb_service.set_ak(os.getenv("VIKINGDB_AK"))
vikingdb_service.set_sk(os.getenv("VIKINGDB_SK"))

# Get the index (do this once during initialization)
index = vikingdb_service.get_index("Ankur_NewsChatbot_Collection", "Ankur_NewsChatbot_Index")

# Define available categories
CATEGORIES = ["business", "sports", "international", "politics", "bollywood"]

# Define available languages (from the language mapping in upload_news_dataset.py)
LANGUAGES = {
    "hindi": "Hindi",
    "gujarati": "Gujarati",
    "tamil": "Tamil",
    "telugu": "Telugu",
    "malayalam": "Malayalam",
    "marathi": "Marathi",
    "bengali": "Bengali",
    "kannada": "Kannada",
    "oriya": "Oriya",
    "punjabi": "Punjabi",
    "assamese": "Assamese",
    "all": "All Languages"
}

# Function to search for news articles
def search_news_articles(query, limit=3, language=None):
    try:
        # We'll retrieve more results than needed to allow for post-filtering by language
        search_limit = limit * 10 if language and language != "all" else limit
        post_process_input_limit = search_limit * 2  # Double the input limit for post-processing
        
        # Prepare search parameters
        search_params = {
            "text": query,  # Use the input query as search text
            "limit": search_limit,  # Number of results to return
            "need_instruction": False,
            "output_fields": ["id", "headline", "summary", "category", "url", "imageurl", "language"]
        }
        
        # Add language filter using post-processing operators if a specific language is selected
        if language and language != "all":
            # Get the full language name (both lowercase for case-insensitive comparison)
            language_full = LANGUAGES.get(language, language)
            
            # Create a string_match post-processing operator for language filtering
            # This uses a case-insensitive regex pattern to match the language
            language_pattern = f"(?i)^{language}$|^{language_full}$"
            
            post_process_op = {
                "op": "string_match",
                "field": "language",
                "pattern": language_pattern
            }
            
            # Add the post-processing operator to search parameters
            search_params["post_process_ops"] = [post_process_op]
            search_params["post_process_input_limit"] = post_process_input_limit
            
            # Log the post-processing operator being applied
            print(f"DEBUG - Applying language post-processing: {post_process_op}")
        
        # Search for similar news articles using multimodal search with post-processing
        results = index.search_with_multi_modal(**search_params)
        
        # Log the IDs of all retrieved articles
        if results:
            article_ids = [result.fields.get('id', 'unknown') for result in results]
            print(f"DEBUG - Articles found: {article_ids}")
            
            # Limit the results to the requested number
            results = results[:limit]
            
            # Log the final set of articles being returned
            final_ids = [result.fields.get('id', 'unknown') for result in results]
            print(f"DEBUG - Final articles returned: {final_ids}")
        
        return results
    except Exception as e:
        st.error(f"Error searching for news articles: {str(e)}")
        print(f"ERROR - {str(e)}")
        return []

# Function to display news articles in card format
def display_news_cards(results):
    if not results:
        st.info("No relevant news articles found. Try a different query or category.")
        return
    
    # Display the results in a card format
    for i, result in enumerate(results, 1):
        fields = result.fields
        score = result.score
        
        # Create a card-like display for each article
        with st.container():
            cols = st.columns([1, 3])
            
            # Column 1: Image (if available)
            with cols[0]:
                if fields.get('imageurl') and fields['imageurl'].strip():
                    try:
                        st.image(fields['imageurl'], width=150)
                    except Exception:
                        st.image("https://ankurdemo.tos-ap-southeast-1.bytepluses.com/newsArticle/default.jpeg", width=150)
                else:
                    st.image("https://ankurdemo.tos-ap-southeast-1.bytepluses.com/newsArticle/default.jpeg", width=150)
            
            # Column 2: Article details
            with cols[1]:
                st.markdown(f"### {fields['headline']}")
                st.markdown(f"**Category:** {fields.get('category', 'General')}")
                if fields.get('language'):
                    st.markdown(f"**Language:** {fields.get('language', 'Unknown')}")
                if fields.get('url') and fields['url'].strip():
                    st.markdown(f"[Read full article]({fields['url']})")
                st.markdown(f"**Relevance Score:** {score:.2f}")
                st.markdown(f"id: {fields['id']}")
            
            st.markdown("---")

# Initialize session state for chat history if it doesn't exist
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# Main Streamlit UI
st.title("News Article Chatbot")
st.write("Discover news articles based on your interests. Type a query or select a category below.")

# Sidebar for app information
with st.sidebar:
    st.title("About")
    st.info(
        "This is a RAG-based chatbot that helps you discover news articles "
        "based on your interests. You can search by typing queries or selecting "
        "categories."
    )
    
    # Add credits or additional information
    st.markdown("### Data Source")
    st.write("News articles from various Indian publications in multiple languages.")

# Add a button to clear chat history - moved to top to ensure it's processed first
if st.button("Clear Chat History"):
    st.session_state.chat_history = []
    st.rerun()

# Language selection dropdown
st.write("### Select Language")
selected_language = st.selectbox(
    "Select language for search results:",
    options=list(LANGUAGES.keys()),
    format_func=lambda x: LANGUAGES[x],
    index=list(LANGUAGES.keys()).index("all")
)

# Category selection buttons
st.write("### Categories")
category_cols = st.columns(len(CATEGORIES))
selected_category = None

# Create grey buttons for categories
for i, category in enumerate(CATEGORIES):
    with category_cols[i]:
        if st.button(category, key=f"cat_{category}", use_container_width=True):
            selected_category = category

# Chat input
st.write("### Chat")
user_query = st.text_input("Ask about news or enter a topic you're interested in:")

# Process user input (either from text input or category selection)
if user_query or selected_category:
    query = user_query if user_query else selected_category
    
    # Add user query to chat history
    st.session_state.chat_history.append({"role": "user", "content": query})
    
    # Search for relevant news articles
    with st.spinner('Searching for relevant news articles...'):
        results = search_news_articles(query, limit=3, language=selected_language)
    
    # Generate a response based on the results
    if results:
        response = f"Here are some news articles about '{query}':"
    else:
        response = f"I couldn't find any news articles about '{query}'. Try a different query or category."
    
    # Add bot response to chat history
    st.session_state.chat_history.append({"role": "assistant", "content": response})

# Custom CSS for chat messages
st.markdown("""
<style>
.user-message {
    background-color: #808080;
    color: white;
    padding: 15px;
    border-radius: 10px;
    margin: 10px 0;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}
.bot-message {
    background-color: #add8e6;
    color: black;
    padding: 15px;
    border-radius: 10px;
    margin: 10px 0;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}
</style>
""", unsafe_allow_html=True)

# Display chat history
for message in st.session_state.chat_history:
    if message["role"] == 'user':
        st.markdown(f"""
        <div class="user-message">
            <strong>You:</strong> {message['content']}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="bot-message">
            <strong>News Bot:</strong> {message['content']}
        </div>
        """, unsafe_allow_html=True)

# Display news article cards if we have results from the current query
if user_query or selected_category:
    st.write("### Relevant News Articles")
    display_news_cards(results)