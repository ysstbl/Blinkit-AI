import random
import psycopg2
from sentence_transformers import SentenceTransformer

# 1. Paste your working Supabase pooler URL here
DATABASE_URL = "postgresql://postgres.rgsfjtqmzcunqcftjufv:blinkitproject2026@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"

print("Loading embedding model...")
model = SentenceTransformer('all-MiniLM-L6-v2')

# 2. The missing CATEGORIES dictionary
CATEGORIES = {
    "Dairy": [
        ("Amul Fresh Paneer 200g", 95, "200g"),
        ("Milky Mist Paneer 200g", 110, "200g"),
        ("Amul Taaza Toned Milk 1L", 56, "1L"),
        ("Dairy Best Cooking Cream 200ml", 85, "200ml"),
        ("Amul Fresh Cream 250ml", 70, "250ml")
    ],
    "Produce": [
        ("Hybrid Tomato 500g", 24, "500g"),
        ("Red Onion 1kg", 38, "1kg"),
        ("Fresh Coriander Leaves 100g", 15, "100g")
    ],
    "Spices & Staples": [
        ("Catch Kasuri Methi 50g", 42, "50g"),
        ("Everest Kasoori Methi 25g", 28, "25g"),
        ("MDH Garam Masala 100g", 92, "100g")
    ]
}

def initialize_catalog():
    print("Connecting to Supabase...")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("Setting up database schema...")
    # 1. Automatically enable pgvector and create the table if it's missing
    cur.execute("""
        CREATE EXTENSION IF NOT EXISTS vector;
        
        CREATE TABLE IF NOT EXISTS grocery_catalog (
            sku_id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            category VARCHAR(100),
            pack_size VARCHAR(50),
            price NUMERIC(10, 2),
            in_stock BOOLEAN,
            stock_qty INTEGER,
            dark_store_id VARCHAR(50),
            embedding VECTOR(384) 
        );
    """)
    conn.commit()
    print("Schema ready! Inserting products...")
    
    sku_counter = 1000
    
    for category, items in CATEGORIES.items():
        for name, price, pack_size in items:
            sku_counter += 1
            sku_id = f"SKU_{sku_counter}"
            
            in_stock = False if "Dairy Best" in name or "Catch" in name else True
            stock_qty = 0 if not in_stock else random.randint(10, 50)
            
            text_to_embed = f"{name} {category}"
            embedding = model.encode(text_to_embed).tolist()
            
            cur.execute("""
                INSERT INTO grocery_catalog 
                (sku_id, name, category, pack_size, price, in_stock, stock_qty, dark_store_id, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (sku_id) DO NOTHING;
            """, (sku_id, name, category, pack_size, price, in_stock, stock_qty, "DS_BLR_01", embedding))
            
    conn.commit()
    cur.close()
    conn.close()
    print(f"Mock catalog populated successfully with embeddings for {sku_counter - 1000} SKUs.")

if __name__ == "__main__":
    initialize_catalog()