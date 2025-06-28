import streamlit as st
from volcengine.viking_db import *
import os
from dotenv import load_dotenv
import re

# Load environment variables from .env file
load_dotenv()

# Initialize VikingDB service
vikingdb_service = VikingDBService(os.getenv("VIKINGDB_ENDPOINT"), os.getenv("VIKINGDB_REGION"))
vikingdb_service.set_ak(os.getenv("VIKINGDB_AK"))
vikingdb_service.set_sk(os.getenv("VIKINGDB_SK"))

# Get the index (do this once during initialization)
index = vikingdb_service.get_index("Ankur_NewsRAG_Collection", "Ankur_NewsRAG_Index")

# Define available categories
CATEGORIES = ["business", "sports", "international", "politics", "bollywood"]

# Define available languages
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
def search_news_articles(query, limit=3, language=None, category=None):
    try:
        # Scenario 1: Category button clicked (category-based filtering)
        if category and not query:
            search_params = {
                "text": category,
                "limit": limit,
                "filter": {
                    "op": "and",
                    "conds": [
                        {"op": "must", "field": "language", "conds": [language]},
                        {"op": "must", "field": "category", "conds": [category]}
                    ]
                } if language and language != "all" else {
                    "op": "must",
                    "field": "category",
                    "conds": [category]
                },
                "need_instruction": False,
                "output_fields": ["id", "headline", "summary", "category", "url", "imageurl", "language", "publishdate"]
            }
        
        # Scenario 2: User typed query (semantic search)
        else:
            search_params = {
                "text": query,
                "limit": 50,  # Get more results to ensure we have enough per category
                "filter": {
                    "op": "must",
                    "field": "language",
                    "conds": [language]
                } if language and language != "all" else None,
                "need_instruction": False,
                "output_fields": ["id", "headline", "summary", "category", "url", "imageurl", "language", "publishdate"]
            }
        
        # Search for articles using multimodal search
        results = index.search_with_multi_modal(**search_params)
        
        # Log the search results for debugging
        if results:
            print(f"Found {len(results)} results for query: {query or category}")
            
            # Scenario 2: Post-process results for semantic search
            if not category and query:
                # Group results by category while preserving relevance order
                category_groups = {}
                for result in results:
                    cat = result.fields.get('category', 'unknown')
                    if cat not in category_groups:
                        category_groups[cat] = []
                    category_groups[cat].append(result)
                
                # Sort each category group by relevance score (highest first)
                for cat in category_groups:
                    category_groups[cat].sort(
                        key=lambda x: x.score, 
                        reverse=True
                    )
                
                # Calculate category relevance (average score of top 3 results per category)
                category_relevance = {}
                for cat, cat_results in category_groups.items():
                    top_results = cat_results[:3]
                    avg_score = sum(r.score for r in top_results) / len(top_results)
                    category_relevance[cat] = avg_score
                
                # Sort categories by relevance
                sorted_categories = sorted(category_relevance.keys(), 
                                         key=lambda x: category_relevance[x], 
                                         reverse=True)
                
                # Select up to 3 results per category, prioritizing most relevant categories
                final_results = []
                max_results_per_category = 3
                
                for cat in sorted_categories:
                    if len(final_results) >= limit:
                        break
                    
                    cat_results = category_groups[cat][:max_results_per_category]
                    remaining_slots = limit - len(final_results)
                    
                    # Add results from this category
                    for result in cat_results[:remaining_slots]:
                        final_results.append(result)
                        if len(final_results) >= limit:
                            break
                
                print(f"Final results distribution: {[(r.fields.get('category'), r.fields.get('id'), r.score) for r in final_results]}")
                return final_results
            
            # Scenario 1: Sort by publishdate for category search
            else:
                results.sort(
                    key=lambda x: x.fields.get('publishdate', ''), 
                    reverse=True
                )
        
        # Return only the top 'limit' results
        return results[:limit]
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
                        # Use a default image if the provided URL fails
                        st.image("https://ankurdemo.tos-ap-southeast-1.bytepluses.com/newsArticle/default.jpeg", width=150)
                else:
                    # Use a default image if no image URL is provided
                    st.image("https://ankurdemo.tos-ap-southeast-1.bytepluses.com/newsArticle/default.jpeg", width=150)
            
            # Column 2: Article details
            with cols[1]:
                st.markdown(f"### {fields['headline']}")
                st.markdown(f"**Category:** {fields.get('category', 'General')}")
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

# Add a button to clear chat history - placed at the top to ensure it's processed first
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
        results = search_news_articles(
            query, 
            limit=3, 
            language=selected_language, 
            category=selected_category
        )
    
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