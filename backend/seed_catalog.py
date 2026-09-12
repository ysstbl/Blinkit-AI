import os
import time
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import google.generativeai as genai
from dotenv import load_dotenv
import uuid
import random
import kagglehub

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

print("Fetching dataset from Kaggle...")
dataset_folder = kagglehub.dataset_download("surajjha101/bigbasket-entire-product-list-28k-datapoints")
csv_path = os.path.join(dataset_folder, "BigBasket Products.csv")

df = pd.read_csv(csv_path)
df = df.dropna(subset=['product', 'sale_price'])

staple_keywords = 'Tomato|Paneer|Onion|Garlic|Chilli|Potato|Milk|Dal|Rice|Salt|Sugar|Coriander|Chicken|Egg|Butter|Oil'
staples_df = df[df['product'].str.contains(staple_keywords, case=False, na=False)]
random_df = df.sample(n=1400, random_state=42)
df = pd.concat([staples_df, random_df]).drop_duplicates(subset=['product']).head(1400).reset_index(drop=True)

df['enriched_text'] = "Category: " + df['category'].astype(str) + " | Product: " + df['product'].astype(str)
texts = df['enriched_text'].tolist()

print("Connecting to Supabase and clearing old data...")
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
#cur.execute("TRUNCATE TABLE grocery_catalog;")
conn.commit()

print(f"Generating and saving vectors for {len(texts)} items in real-time...")
batch_size = 90  
i = 0

insert_query = """
    INSERT INTO grocery_catalog (sku_id, name, price, in_stock, pack_size, embedding) 
    VALUES %s
"""

while i < len(texts):
    batch = texts[i:i + batch_size]
    batch_df = df.iloc[i:i + batch_size]
    
    try:
        response = genai.embed_content(
            model="models/gemini-embedding-001",
            content=batch,
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=768
        )
        
        # Instantly prepare and insert this exact batch
        records = []
        for idx, row in enumerate(batch_df.itertuples()):
            records.append((
                str(uuid.uuid4()),                  
                row.product,                     
                float(row.sale_price),           
                random.choice([True, True, False]), 
                str(getattr(row, 'quantity', '1 pc')),   
                str(response['embedding'][idx])  
            ))
            
        execute_values(cur, insert_query, records)
        conn.commit() # Save directly to Supabase immediately
        
        i += batch_size
        print(f"✅ Saved {i}/{len(texts)} items to database.")
        
        if i < len(texts):
            print("Sleeping 62 seconds to respect API quota...")
            time.sleep(62)
            
    except Exception as e:
        print(f"Rate limit hit! Cooling down for 20 seconds before retrying...")
        time.sleep(20)

cur.close()
conn.close()
print("✅ Finished seeding database safely!")