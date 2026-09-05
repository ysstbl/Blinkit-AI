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

app = FastAPI(title="Blinkit AI Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
llm_model = genai.GenerativeModel('gemini-1.5-flash')
embed_model = SentenceTransformer('all-MiniLM-L6-v2')
DB_URL = os.getenv("DATABASE_URL")

# --- 1. DATA MODELS ---
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
    raw_matches: list[MatchedSKU]

# --- 2. LLM SCHEMAS ---
intent_schema = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["INVENTORY_QUERY", "RECIPE_EXTRACTION"]},
        "cleaned_query": {"type": "string", "description": "The core product or recipe query"}
    },
    "required": ["intent", "cleaned_query"]
}

recipe_schema = {
    "type": "object",
    "properties": {
        "dish_name": {"type": "string"},
        "ingredients": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "canonical_name": {"type": "string"},
                    "quantity": {"type": "string"},
                    "is_pantry_staple": {"type": "boolean"}
                },
                "required": ["canonical_name", "quantity", "is_pantry_staple"]
            }
        }
    },
    "required": ["dish_name", "ingredients"]
}

# --- 3. HELPER FUNCTIONS ---
def search_catalog(ingredient_name: str) -> list[MatchedSKU]:
    """Convert string to vector and search pgvector database"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    vector = embed_model.encode(ingredient_name).tolist()
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

def extract_recipe_cart(prompt: str) -> list[IngredientMatch]:
    """Extract ingredients and handle out-of-stock substitutions"""
    response = llm_model.generate_content(
        f"Extract the recipe ingredients for: {prompt}",
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=recipe_schema
        )
    )
    
    try:
        parsed_data = json.loads(response.text)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse LLM output")

    final_cart = []
    for item in parsed_data.get("ingredients", []):
        skus = search_catalog(item["canonical_name"])
        selected_sku = None
        is_substituted = False
        original_sku = None
        
        if skus:
            primary_match = skus[0] 
            if primary_match.in_stock:
                selected_sku = primary_match
            else:
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

# --- 4. MAIN ROUTER ENDPOINT ---
@app.post("/api/blinkit-assistant")
async def blinkit_assistant(request: RecipeRequest):
    """Classifies user intent and routes to the correct logic pipeline"""
    
    # Step A: Classify Intent
    router_prompt = f"Classify the following user query: '{request.prompt}'"
    router_response = llm_model.generate_content(
        router_prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=intent_schema
        )
    )
    
    try:
        routing = json.loads(router_response.text)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse intent")

    intent = routing.get("intent")
    query = routing.get("cleaned_query")

    # Step B: Handle direct inventory questions
    if intent == "INVENTORY_QUERY":
        skus = search_catalog(query)
        if not skus:
            return {"type": "chat", "message": f"Sorry, I couldn't find any products matching '{query}'. Check spelling or try a broader term."}
        
        top_match = skus[0]
        status = f"in stock (₹{top_match.price} for {top_match.pack_size})" if top_match.in_stock else "currently out of stock"
        return {
            "type": "chat", 
            "message": f"Yes, {top_match.name} is {status}."
        }

    # Step C: Handle complex recipe building
    elif intent == "RECIPE_EXTRACTION":
        cart = extract_recipe_cart(request.prompt)
        return {"type": "recipe_cart", "data": cart}