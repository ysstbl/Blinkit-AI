import os
import json
import re
import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from sentence_transformers import SentenceTransformer

load_dotenv()

# Load the local vector model to bypass all API limits
embed_model = SentenceTransformer('all-MiniLM-L6-v2')

app = FastAPI(title="Blinkit AI Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure LLM for the text reasoning (recipe extraction/routing)
genai.configure(api_key=os.getenv("GEMINI_API_KEY")) rf
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
    substitution_reason: str | None = None
    raw_matches: list[MatchedSKU]

# --- 2. LLM SCHEMAS ---
intent_schema = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["INVENTORY_QUERY", "CATALOG_QUERY", "RECIPE_EXTRACTION", "CHAT"]},
        "query_type": {
            "type": "string",
            "enum": ["CHEAPEST_ITEM", "MOST_EXPENSIVE_ITEM", "CHAT"],
        },
        "cleaned_query": {"type": "string", "description": "The core product or recipe query"}
    },
    "required": ["intent", "query_type", "cleaned_query"]
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
    """Search pgvector using local embeddings and fuzzy lexical re-ranking."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # 1. Generate local vector with lightweight prefix
    enriched_query = f"Product: {ingredient_name}"
    vector = embed_model.encode(enriched_query).tolist()
    
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
        'snack', 'ready', 'mix', 'masala', 'ketchup', 'soup', 'cake', 'butter'
    }
    fresh_boost_flags = {'fresho', 'fresh', 'organic', 'raw', 'whole'}
    
    def calculate_relevance(row):
        name = row[1].lower()
        name_terms = set(name.replace('-', ' ').split())
        
        # FUZZY OVERLAP
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
    if not results or calculate_relevance(results[0]) <= 0:
        return []
    
    return [
        MatchedSKU(sku_id=row[0], name=row[1], price=row[2], in_stock=row[3], pack_size=row[4])
        for row in results[:15]
    ]

def extract_recipe_cart(prompt: str) -> list[IngredientMatch]:
    """Extract ingredients and handle out-of-stock substitutions"""
    localization_prompt = f"""
    Extract the recipe ingredients for: {prompt}.
    IMPORTANT INSTRUCTIONS:
    1. Translate Western ingredient names into standard Indian grocery terms (e.g., 'bell pepper' -> 'capsicum', 'cilantro' -> 'coriander leaves').
    2. CRITICAL: Strip ALL preparation adjectives, measurements, and physical forms. (e.g., 'minced ginger' -> 'ginger', 'sliced onion' -> 'onion').
    3. Keep names strictly to the raw base ingredient unless a processed version is specifically requested.
    4. Be precise with every ingredient (e.g., don't give 'oil', be specific 'mustard oil'/'olive oil').
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
        substitution_reason = None
        
        if skus:
            primary_match = skus[0] 
            if primary_match.in_stock:
                selected_sku = primary_match
            else:
                original_sku = primary_match
                is_substituted = True
                substitution_reason = "The closest catalog match is out of stock."
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
            substitution_reason=substitution_reason,
            raw_matches=skus
        ))
    return final_cart

def create_product_checklist(query: str) -> IngredientMatch | None:
    """Turn a product request into a staged checklist item."""
    skus = search_catalog(query)
    if not skus:
        return None

    primary_match = skus[0]
    selected_sku = primary_match if primary_match.in_stock else None
    original_sku = None
    substitution_reason = None

    if not primary_match.in_stock:
        original_sku = primary_match
        for fallback in skus[1:]:
            if fallback.in_stock:
                selected_sku = fallback
                break
        if selected_sku:
            substitution_reason = "The closest catalog match is out of stock."

    return IngredientMatch(
        canonical_name=query,
        quantity="1",
        is_pantry_staple=False,
        selected_sku=selected_sku,
        is_substituted=bool(original_sku and selected_sku),
        original_sku=original_sku,
        substitution_reason=substitution_reason,
        raw_matches=skus,
    )

def answer_catalog_query(query_type: str, catalog_filter: str = "") -> str:
    """Answer catalog price questions, optionally narrowed to a product category."""
    order = "ASC" if query_type == "CHEAPEST_ITEM" else "DESC"
    label = "cheapest" if query_type == "CHEAPEST_ITEM" else "most expensive"
    filter_terms = [term for term in catalog_filter.lower().split() if len(term) > 1]
    filter_sql = ""
    filter_params = []
    if filter_terms:
        conditions = []
        for term in filter_terms:
            conditions.append("(name ILIKE %s OR category ILIKE %s)")
            wildcard = f"%{term}%"
            filter_params.extend([wildcard, wildcard])
        filter_sql = " AND " + " AND ".join(conditions)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute(f"""
        SELECT name, price, pack_size
        FROM grocery_catalog
        WHERE in_stock = TRUE AND price IS NOT NULL{filter_sql}
        ORDER BY price {order}
        LIMIT 1;
    """, filter_params)
    result = cur.fetchone()
    cur.close()
    conn.close()

    if not result:
        scope = f" matching '{catalog_filter}'" if filter_terms else ""
        return f"I couldn't find an in-stock item{scope} to identify as the {label} item right now."

    name, price, pack_size = result
    scope = f" {catalog_filter}" if filter_terms else ""
    return f"The {label}{scope} in-stock item is {name} at ₹{price} for {pack_size}."

def extract_catalog_filter(prompt: str, cleaned_query: str | None) -> str:
    """Remove price-question language and keep the requested product/category terms."""
    source = cleaned_query or prompt
    source = re.sub(
        r"\b(cheapest|most expensive|lowest price|highest price|price|item|items|product|products|in stock|available|is|are|the|what|whats|what's|please|show|me|find)\b",
        " ",
        source.lower(),
    )
    return " ".join(source.split())

# --- 4. MAIN ROUTER ENDPOINT ---
@app.post("/api/blinkit-assistant")
async def blinkit_assistant(request: RecipeRequest):
    router_prompt = f"""
    Classify this grocery assistant message: '{request.prompt}'
    Use RECIPE_EXTRACTION when the user asks what to buy for a dish or recipe.
    Use INVENTORY_QUERY when the user is asking for a specific product or wants to add a product.
    Use CATALOG_QUERY for questions about the catalog as a whole, such as cheapest, most expensive,
    or price comparisons. Use CHAT for general conversation that needs no catalog lookup.
    For CATALOG_QUERY, set query_type to CHEAPEST_ITEM or MOST_EXPENSIVE_ITEM.
    For other intents, set query_type to CHAT and cleaned_query to the product or topic.
    """
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
    query_type = routing.get("query_type", "CHAT")
    query = routing.get("cleaned_query")
    normalized_prompt = request.prompt.lower()
    if "cheapest" in normalized_prompt or "lowest price" in normalized_prompt:
        intent = "CATALOG_QUERY"
        query_type = "CHEAPEST_ITEM"
    elif "most expensive" in normalized_prompt or "highest price" in normalized_prompt:
        intent = "CATALOG_QUERY"
        query_type = "MOST_EXPENSIVE_ITEM"

    if intent == "CATALOG_QUERY":
        catalog_filter = extract_catalog_filter(request.prompt, query)
        return {"type": "chat", "message": answer_catalog_query(query_type, catalog_filter)}

    elif intent == "CHAT":
        response = llm_model.generate_content(
            f"Reply naturally and briefly to this grocery assistant message: '{request.prompt}'. "
            "Do not claim to have searched the catalog or changed the cart.",
        )
        return {"type": "chat", "message": response.text.strip()}

    elif intent == "INVENTORY_QUERY":
        item = create_product_checklist(query)
        if not item:
            return {
                "type": "chat",
                "message": (
                    f"I couldn't find '{query}' in the catalog, so I haven't added anything "
                    "to the checklist."
                ),
            }
        if item.is_substituted:
            message = (
                f"'{item.canonical_name}' is out of stock. I found '{item.selected_sku.name}' "
                "as the closest available match. Please confirm it in the checklist."
            )
        elif not item.selected_sku:
            message = (
                f"'{item.canonical_name}' is currently out of stock and I couldn't find an "
                "available substitute."
            )
        else:
            message = f"I found '{item.selected_sku.name}'. Review it in the checklist before adding it to your cart."
        return {"type": "checklist", "message": message, "data": [item]}

    elif intent == "RECIPE_EXTRACTION":
        cart = extract_recipe_cart(request.prompt)
        return {
            "type": "checklist",
            "message": "I prepared these items for review. Select or unselect anything before adding them to your cart.",
            "data": cart,
        }