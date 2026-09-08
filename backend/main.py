import os
import json
import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
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
# Using gemini-1.5-flash for maximum stability
llm_model = genai.GenerativeModel('gemini-3.1-flash-lite')
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
    """Search pgvector using Google's embeddings and fuzzy lexical re-ranking."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # 1. Generate the search vector (Forced to 768 dimensions to match database)
    embedding_response = genai.embed_content(
        model="models/gemini-embedding-001",
        content=ingredient_name,
        task_type="RETRIEVAL_QUERY",
        output_dimensionality=768
    )
    vector = embedding_response['embedding']
    
    # 2. Cast a wide semantic net
    cur.execute("""
        SELECT sku_id, name, price, in_stock, pack_size
        FROM grocery_catalog
        ORDER BY embedding <=> %s::vector
        LIMIT 30; 
    """, (vector,))
    results = cur.fetchall()
    cur.close()
    conn.close()

    # 3. Fuzzy Lexical Anti-Drift Re-ranker
    query_terms = set(ingredient_name.lower().split())
    
    processed_flags = {
        'pickle', 'paste', 'sauce', 'powder', 'puree', 
        'crushed', 'juice', 'extract', 'syrup', 'frozen',
        'spread', 'dip', 'dressing', 'mayo', 'chips',
        'snack', 'ready', 'mix', 'masala', 'ketchup', 'soup'
    }
    fresh_boost_flags = {'fresho', 'fresh', 'organic', 'raw', 'whole'}
    
    def calculate_relevance(row):
        name = row[1].lower()
        name_terms = set(name.replace('-', ' ').split())
        
        # FUZZY OVERLAP: "soy" matches "soya", "chilli" matches "chillies"
        overlap = 0
        for q_term in query_terms:
            for n_term in name_terms:
                if q_term in n_term or n_term in q_term:
                    overlap += 1
                    break 
        
        has_processed_flag = any(flag in name_terms for flag in processed_flags)
        wants_processed = any(flag in query_terms for flag in processed_flags)
        has_fresh_flag = any(flag in name_terms for flag in fresh_boost_flags)
        
        processed_penalty = 8.0 if (has_processed_flag and not wants_processed) else 0.0
        processed_boost = 4.0 if (has_processed_flag and wants_processed) else 0.0
        fresh_boost = 3.0 if (has_fresh_flag and not wants_processed) else 0.0
        
        extra_words = len(name_terms) - overlap
        length_penalty = extra_words * 0.1
        
        return overlap + fresh_boost + processed_boost - processed_penalty - length_penalty

    results.sort(key=calculate_relevance, reverse=True)
    
    return [
        MatchedSKU(sku_id=row[0], name=row[1], price=row[2], in_stock=row[3], pack_size=row[4])
        for row in results[:3]
    ]

def extract_recipe_cart(prompt: str) -> list[IngredientMatch]:
    """Extract ingredients and handle out-of-stock substitutions with regional localization"""
    
    # CRITICAL FIX: Strips culinary adjectives before searching
    localization_prompt = f"""
    Extract the recipe ingredients for: {prompt}.
    IMPORTANT INSTRUCTIONS:
    1. Translate Western ingredient names into standard Indian grocery terms (e.g., 'bell pepper' -> 'capsicum', 'cilantro' -> 'coriander leaves', 'eggplant' -> 'brinjal', 'soy sauce' -> 'soya sauce').
    2. CRITICAL: Strip ALL preparation adjectives, measurements, and physical forms. (e.g., 'minced ginger' -> 'ginger', 'garlic cloves' -> 'garlic', 'chopped tomatoes' -> 'tomato', 'sliced onion' -> 'onion').
    3. Keep names strictly to the raw base ingredient unless a processed version is specifically requested.
    """
    
    response = llm_model.generate_content(
        localization_prompt,
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

    if intent == "INVENTORY_QUERY":
        skus = search_catalog(query)
        if not skus:
            return {"type": "chat", "message": f"Sorry, I couldn't find any products matching '{query}'."}
        
        top_match = skus[0]
        status = f"in stock (₹{top_match.price} for {top_match.pack_size})" if top_match.in_stock else "currently out of stock"
        return {"type": "chat", "message": f"Yes, {top_match.name} is {status}."}

    elif intent == "RECIPE_EXTRACTION":
        cart = extract_recipe_cart(request.prompt)
        return {"type": "recipe_cart", "data": cart}