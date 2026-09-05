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

print("Loading embedding model...")
embed_model = SentenceTransformer('all-MiniLM-L6-v2')

print("Downloading BigBasket dataset from Kaggle...")
# Your kagglehub snippet
dataset_path = kagglehub.dataset_download("surajjha101/bigbasket-entire-product-list-28k-datapoints")

# Find the CSV file inside the downloaded folder
csv_file = glob.glob(os.path.join(dataset_path, "*.csv"))[0]
print(f"Found dataset at: {csv_file}")

print("Reading and cleaning dataset...")
df = pd.read_csv(csv_file)

# Clean the data: drop rows without names or prices
df = df.dropna(subset=['product', 'sale_price'])

# Take a 5,000 item subset to keep the initial vector generation under 2 minutes
df = df.sample(n=5000, random_state=42).reset_index(drop=True)

print(f"Generating vector embeddings for {len(df)} products (This will take a minute)...")
embeddings = embed_model.encode(df['product'].tolist(), show_progress_bar=True)

# Prepare the data payload
records = []
for idx, row in df.iterrows():
    records.append((
        str(uuid.uuid4()),                  # sku_id
        str(row['product']),                # name
        float(row['sale_price']),           # price
        random.choice([True, True, False]), # in_stock (simulating some out-of-stock)
        # Kaggle dataset often lacks strict pack_sizes, so we fall back gracefully
        str(row.get('quantity', '1 pc')),   
        embeddings[idx].tolist()            # embedding vector
    ))

print("Connecting to Supabase...")
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

print("Clearing old mock catalog and uploading real data...")
cur.execute("TRUNCATE TABLE grocery_catalog;")

insert_query = """
    INSERT INTO grocery_catalog (sku_id, name, price, in_stock, pack_size, embedding) 
    VALUES %s
"""

execute_values(cur, insert_query, records)

conn.commit()
cur.close()
conn.close()

print("✅ Successfully scaled database with real grocery data!")