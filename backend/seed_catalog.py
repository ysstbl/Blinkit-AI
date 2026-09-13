import os
import glob
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import uuid
import random
import kagglehub

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

print("Loading local MiniLM model...")
embed_model = SentenceTransformer('all-MiniLM-L6-v2')

print("Downloading full dataset...")
dataset_path = kagglehub.dataset_download("surajjha101/bigbasket-entire-product-list-28k-datapoints")
csv_file = glob.glob(os.path.join(dataset_path, "*.csv"))[0]

df = pd.read_csv(csv_file)
df = df.dropna(subset=['product', 'sale_price']).reset_index(drop=True)
df['enriched_text'] = "Category: " + df['category'].astype(str) + " | Sub-category: " + df['sub_category'].astype(str) + " | Product: " + df['product'].astype(str)
print(f"Generating vectors for all {len(df)} items locally...")
embeddings = embed_model.encode(df['enriched_text'].tolist(), show_progress_bar=True)

print("Uploading to Supabase (this takes about 10 seconds)...")
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("TRUNCATE TABLE grocery_catalog;")

records = []
for idx, row in df.iterrows():
    records.append((
        str(uuid.uuid4()),                  
        str(row['product']),                
        float(row['sale_price']),           
        random.choice([True, True, False]), 
        str(row.get('quantity', '1 pc')),   
        str(embeddings[idx].tolist())  
    ))

# page_size=1000 ensures massive uploads don't crash PostgreSQL
execute_values(cur, """
    INSERT INTO grocery_catalog (sku_id, name, price, in_stock, pack_size, embedding) 
    VALUES %s
""", records, page_size=1000)

conn.commit()
cur.close()
conn.close()
print("✅ Entire 28k database seeded instantly!")