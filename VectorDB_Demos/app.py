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
index = vikingdb_service.get_index("Ankur_Music_Collection", "Ankur_Music_Index")

def search_similar_songs(song_name):
    try:
        # Search for similar songs using multimodal search
        results = index.search_with_multi_modal(
            text=song_name,  # Use the input song name as search text
            limit=5,  # Get top 5 similar songs
            need_instruction=False,
            output_fields=["song", "artist", "year", "genre", "popularity", "energy"]
        )
        return results
    except Exception as e:
        st.error(f"Error searching for songs: {str(e)}")
        return []

def search_similar_energy_songs(energy_value, song_name):
    try:
        # Search for songs with similar energy levels
        results = index.search_with_multi_modal(
            text=song_name,  # We need to provide text parameter
            limit=20,  # Get more results initially to filter
            need_instruction=False,
            output_fields=["song", "artist", "year", "genre", "popularity", "energy"]
        )
        
        # Filter results manually for similar energy
        filtered_results = []
        for result in results:
            if abs(result.fields['energy'] - energy_value) <= 0.1:
                filtered_results.append(result)
        
        # Return only top 5 filtered results
        return filtered_results[:5]
        
    except Exception as e:
        st.error(f"Error searching for similar energy songs: {str(e)}")
        return []

# Streamlit UI
st.title("Similar Songs Finder")
st.write("Enter a song name to find similar songs in the collection")

# Input field for song name
song_name = st.text_input("Enter a song name:")

if song_name:
    # Create a spinner while searching
    with st.spinner('Searching for songs...'):
        # Run the search function for similar songs
        similar_results = search_similar_songs(song_name)
        
        # Display similar songs results
        if similar_results:
            st.subheader("Similar Songs:")
            for i, result in enumerate(similar_results, 1):
                fields = result.fields
                score = result.score
                
                # Create a card-like display for each song
                with st.container():
                    st.markdown(f"""
                    #### {i}. {fields['song']}
                    - **Artist:** {fields['artist']}
                    - **Genre:** {fields['genre']}
                    - **Year:** {fields['year']}
                    - **Popularity:** {fields['popularity']}
                    - **Energy Level:** {fields['energy']:.2f}
                    - **Similarity Score:** {score:.2f}
                    """)
                    st.write("---")
            
            # Get energy value from the first result
            energy_value = similar_results[0].fields['energy']
            # Search for similar energy songs
            energy_results = search_similar_energy_songs(energy_value, song_name)
            
            if energy_results:
                st.subheader("You May Also Like (Songs with Similar Energy):")
                for j, energy_result in enumerate(energy_results, 1):
                    e_fields = energy_result.fields
                    # Skip if it's the same song as the search result
                    if e_fields['song'] == song_name:
                        continue
                    
                    with st.container():
                        st.markdown(f"""
                        #### {j}. {e_fields['song']}
                        - **Artist:** {e_fields['artist']}
                        - **Genre:** {e_fields['genre']}
                        - **Year:** {e_fields['year']}
                        - **Popularity:** {e_fields['popularity']}
                        - **Energy Level:** {e_fields['energy']:.2f}
                        """)
                        st.write("---")
        else:
            st.warning("No similar songs found.")