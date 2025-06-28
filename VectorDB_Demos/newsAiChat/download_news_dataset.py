from datasets import load_dataset
import pandas as pd
import os

# List of language codes to download
language_codes = ['hi', 'gu', 'mr', 'bn', 'as', 'ml', 'kn', 'ta', 'te', 'pa', 'or']

def download_and_process_dataset():
    # Create a directory to store the CSV files if it doesn't exist
    os.makedirs('news_data', exist_ok=True)
    
    # Initialize an empty list to store all data
    all_data = []
    
    # Download and process each language dataset
    for lang_code in language_codes:
        print(f"Downloading dataset for language: {lang_code}")
        try:
            # Load the dataset for the current language
            ds = load_dataset("ai4bharat/IndicHeadlineGeneration", lang_code)
            
            # Convert to pandas DataFrame
            train_df = pd.DataFrame(ds['train'])
            
            # Add language code as a column
            train_df['language'] = lang_code
            
            # Rename columns to match our schema
            train_df = train_df.rename(columns={
                'input': 'summary',
                'target': 'headline',
                'url': 'url'
            })
            
            # Add placeholder for imageurl
            train_df['imageurl'] = ''
            
            # Add category (using a placeholder for now)
            train_df['category'] = 'news'
            
            # Save individual language dataset with UTF-8-SIG encoding (UTF-8 with BOM)
            lang_file_path = f"news_data/{lang_code}_news_data.csv"
            train_df.to_csv(lang_file_path, index=False, encoding='utf-8-sig')
            print(f"Saved {len(train_df)} records to {lang_file_path}")
            
            # Append to the combined dataset
            all_data.append(train_df)
            
        except Exception as e:
            print(f"Error processing {lang_code}: {str(e)}")
    
    # Combine all datasets
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        
        # Save the combined dataset with UTF-8-SIG encoding
        combined_file_path = "news_data/all_languages_news_data.csv"
        combined_df.to_csv(combined_file_path, index=False, encoding='utf-8-sig')
        print(f"Saved combined dataset with {len(combined_df)} records to {combined_file_path}")
        
        return combined_file_path
    else:
        print("No data was processed successfully.")
        return None

if __name__ == "__main__":
    download_and_process_dataset()