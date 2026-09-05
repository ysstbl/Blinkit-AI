import os
import json
import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware


load_dotenv()

# 1. Initialize models and config
app = FastAPI(title="Recipe-to-Cart API")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
llm_model = genai.GenerativeModel('gemini-3.1-flash-lite')
embed_model = SentenceTransformer('all-MiniLM-L6-v2')
DB_URL = os.getenv("DATABASE_URL")


# ... existing code ...
app = FastAPI(title="Recipe-to-Cart API")

# Add this CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ... rest of the code ...

# 2. Define Data Models
class RecipeRequest(BaseModel):
    prompt: str

class MatchedSKU(BaseModel):
    sku_id: str
    name: str
    price: float
    in_stock: bool
    pack_size: str

class IngredientMatch(BaseModel):
    canonical_name: str
    quantity: str
    is_pantry_staple: bool
    selected_sku: MatchedSKU | None = None
    is_substituted: bool = False
    original_sku: MatchedSKU | None = None
    raw_matches: list[MatchedSKU] # Keeping this for debugging

# 3. LLM Structured Output Schema
recipe_schema = {
    "type": "object",
    "properties": {
        "dish_name": {"type": "string"},
        "ingredients": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "canonical_name": {"type": "string", "description": "Generic ingredient name, e.g., 'paneer'"},
                    "quantity": {"type": "string", "description": "Amount with unit, e.g., '200g'"},
                    "is_pantry_staple": {"type": "boolean", "description": "True if common spice/oil/salt"}
                },
                "required": ["canonical_name", "quantity", "is_pantry_staple"]
            }
        }
    },
    "required": ["dish_name", "ingredients"]
}

def search_catalog(ingredient_name: str) -> list[MatchedSKU]:
    """Convert ingredient to vector and query Supabase for top 3 matches."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # Create embedding for the ingredient
    vector = embed_model.encode(ingredient_name).tolist()
    
    # Query using pgvector cosine distance (<=>)
    cur.execute("""
        SELECT sku_id, name, price, in_stock, pack_size
        FROM grocery_catalog
        ORDER BY embedding <=> %s::vector
        LIMIT 3;
    """, (vector,))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [
        MatchedSKU(sku_id=row[0], name=row[1], price=row[2], in_stock=row[3], pack_size=row[4])
        for row in results
    ]

@app.post("/api/recipe-to-cart", response_model=list[IngredientMatch])
async def parse_and_match(request: RecipeRequest):
    # A. Parse Recipe with LLM
    prompt = f"Extract the recipe ingredients for: {request.prompt}"
    response = llm_model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=recipe_schema
        )
    )
    
    try:
        parsed_data = json.loads(response.text)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse LLM output")

    # B. Match and Resolve Substitutions
    final_cart = []
    for item in parsed_data.get("ingredients", []):
        # Returns top 3 vector matches
        skus = search_catalog(item["canonical_name"]) 
        
        selected_sku = None
        is_substituted = False
        original_sku = None
        
        if skus:
            # The #1 closest vector match
            primary_match = skus[0] 
            
            if primary_match.in_stock:
                selected_sku = primary_match
            else:
                # Trigger Substitution: find the next closest item that IS in stock
                original_sku = primary_match
                is_substituted = True
                for fallback in skus[1:]:
                    if fallback.in_stock:
                        selected_sku = fallback
                        break
                        
        final_cart.append(IngredientMatch(
            canonical_name=item["canonical_name"],
            quantity=item["quantity"],
            is_pantry_staple=item["is_pantry_staple"],
            selected_sku=selected_sku,
            is_substituted=is_substituted,
            original_sku=original_sku,
            raw_matches=skus
        ))
        
    return final_cart