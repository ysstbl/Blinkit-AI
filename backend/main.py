import os
import json
import re
import urllib.parse
import urllib.request
from time import perf_counter
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from huggingface_hub import InferenceClient
from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

load_dotenv()

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

embedding_client = InferenceClient(token=os.getenv("HF_TOKEN"))
embedding_model = os.getenv(
    "HF_EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)

def create_embedding(text: str) -> list[float]:
    started_at = perf_counter()
    try:
        embedding = embedding_client.feature_extraction(
            text,
            model=embedding_model,
        )
    finally:
        huggingface_duration.record(
            perf_counter() - started_at,
            metric_attributes(provider="huggingface", model=embedding_model),
        )
    return embedding.tolist()

app = FastAPI(title="Blinkit AI Assistant API")

environment = os.getenv("OTEL_ENVIRONMENT", "development")
meter_provider = MeterProvider(
    resource=Resource.create({
        "service.name": "blinkit-ai-api",
        "deployment.environment": environment,
    }),
    metric_readers=[PrometheusMetricReader()],
)
metrics.set_meter_provider(meter_provider)
meter = metrics.get_meter("blinkit-ai-api")
request_duration = meter.create_histogram(
    "blinkit_request_duration",
    unit="s",
    description="Complete assistant request duration",
)
request_count = meter.create_counter(
    "blinkit_requests",
    unit="{request}",
    description="Completed assistant request count",
)
request_errors = meter.create_counter(
    "blinkit_request_errors",
    unit="{error}",
    description="Assistant request errors",
)
gemini_duration = meter.create_histogram(
    "blinkit_gemini_duration",
    unit="s",
    description="Gemini model call duration",
)
huggingface_duration = meter.create_histogram(
    "blinkit_huggingface_embedding_duration",
    unit="s",
    description="Hugging Face embedding call duration",
)
postgres_duration = meter.create_histogram(
    "blinkit_postgresql_query_duration",
    unit="s",
    description="PostgreSQL query duration",
)
database_errors = meter.create_counter(
    "blinkit_database_errors",
    unit="{error}",
    description="PostgreSQL query errors",
)


def metric_attributes(**attributes):
    return {"environment": environment, **attributes}


def generate_gemini_content(*args, **kwargs):
    started_at = perf_counter()
    attributes = metric_attributes(provider="gemini")
    try:
        return llm_model.generate_content(*args, **kwargs)
    finally:
        gemini_duration.record(perf_counter() - started_at, attributes)


def execute_postgres_query(cursor, statement, parameters=None, operation="query"):
    started_at = perf_counter()
    attributes = metric_attributes(operation=operation)
    try:
        return cursor.execute(statement, parameters)
    except psycopg2.Error:
        database_errors.add(1, attributes)
        raise
    finally:
        postgres_duration.record(perf_counter() - started_at, attributes)


def prometheus_query(query):
    prometheus_url = os.getenv("PROMETHEUS_URL")
    if not prometheus_url:
        return None

    query_url = f"{prometheus_url.rstrip('/')}/api/v1/query?{urllib.parse.urlencode({'query': query})}"
    try:
        with urllib.request.urlopen(query_url, timeout=5) as response:
            payload = json.load(response)
    except (OSError, ValueError, json.JSONDecodeError):
        return None

    if payload.get("status") != "success":
        return None
    results = payload.get("data", {}).get("result", [])
    if not results:
        return None
    try:
        return float(results[0]["value"][1])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def prometheus_quantile(metric_name, selector, window, quantile):
    query = (
        f"histogram_quantile({quantile}, "
        f"sum by (le) (rate({metric_name}_bucket{{{selector}}}[{window}])) )"
    )
    value = prometheus_query(query)
    return round(value * 1000, 1) if value is not None else None


def prometheus_p95(metric_name, selector, window):
    return prometheus_quantile(metric_name, selector, window, 0.95)


def prometheus_count(metric_name, selector, window):
    query = f"sum(increase({metric_name}_total{{{selector}}}[{window}]))"
    value = prometheus_query(query)
    return round(value) if value is not None else 0

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"status": "ok", "service": "blinkit-ai-api"}

# Configure LLM for the text reasoning (recipe extraction/routing)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
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
def search_catalog(ingredient_name: str, recipe_context: bool = False) -> list[MatchedSKU]:
    """Search pgvector using local embeddings and fuzzy lexical re-ranking."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # 1. Generate local vector with lightweight prefix
    enriched_query = f"Product: {ingredient_name}"
    vector = create_embedding(enriched_query)
    
    # 2. Cast a wide semantic net
    execute_postgres_query(cur, """
        SELECT sku_id, name, price, in_stock, pack_size, category
        FROM grocery_catalog
        ORDER BY embedding <=> %s::vector
        LIMIT 100; 
    """, (vector,), operation="catalog_search")
    results = cur.fetchall()
    cur.close()
    conn.close()

    # 3. Fuzzy Lexical Anti-Drift Re-ranker
    query_terms = set(ingredient_name.lower().split())
    normalized_query = re.sub(r"[^a-z0-9 ]", " ", ingredient_name.lower())

    non_food_flags = {
        'bleach', 'bathroom', 'cleaner', 'cleaning', 'disinfectant', 'dishwash',
        'drain', 'fabric', 'floor', 'handwash', 'laundry', 'phenyl', 'polish',
        'sanitizer', 'shampoo', 'soap', 'toilet', 'surface', 'detergent',
    }
    food_category_flags = {
        'bakery', 'beverage', 'dairy', 'food', 'fruit', 'grocery', 'meat',
        'produce', 'snack', 'spice', 'staple', 'vegetable',
    }

    def is_food_candidate(row):
        product_text = f"{row[1]} {row[5] or ''}".lower()
        return not any(flag in product_text for flag in non_food_flags)
    
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
        exact_phrase_boost = 5.0 if normalized_query in name else 0.0
        food_category_boost = 1.5 if any(
            flag in (row[5] or '').lower() for flag in food_category_flags
        ) else 0.0
        
        return (
            overlap + exact_phrase_boost + food_category_boost + fresh_boost
            + processed_boost - processed_penalty - length_penalty
        )

    if recipe_context:
        results = [row for row in results if is_food_candidate(row)]
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
    
    response = generate_gemini_content(
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
        skus = search_catalog(item["canonical_name"], recipe_context=True)
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
    execute_postgres_query(cur, f"""
        SELECT name, price, pack_size
        FROM grocery_catalog
        WHERE in_stock = TRUE AND price IS NOT NULL{filter_sql}
        ORDER BY price {order}
        LIMIT 1;
    """, filter_params, operation="catalog_price_query")
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
    started_at = perf_counter()
    intent = "UNKNOWN"
    status_code = "500"
    router_prompt = f"""
    Classify this grocery assistant message: '{request.prompt}'
    Use RECIPE_EXTRACTION when the user asks what to buy for a dish or recipe.
    Use INVENTORY_QUERY when the user is asking for a specific product or wants to add a product.
    Use CATALOG_QUERY for questions about the catalog as a whole, such as cheapest, most expensive,
    or price comparisons. Use CHAT for general conversation that needs no catalog lookup.
    For CATALOG_QUERY, set query_type to CHEAPEST_ITEM or MOST_EXPENSIVE_ITEM.
    For other intents, set query_type to CHAT and cleaned_query to the product or topic.
    """
    try:
        router_response = generate_gemini_content(
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
            response = {"type": "chat", "message": answer_catalog_query(query_type, catalog_filter)}

        elif intent == "CHAT":
            response = generate_gemini_content(
                f"Reply naturally and briefly to this grocery assistant message: '{request.prompt}'. "
                "Do not claim to have searched the catalog or changed the cart.",
            )
            response = {"type": "chat", "message": response.text.strip()}

        elif intent == "INVENTORY_QUERY":
            item = create_product_checklist(query)
            if not item:
                response = {
                    "type": "chat",
                    "message": (
                        f"I couldn't find '{query}' in the catalog, so I haven't added anything "
                        "to the checklist."
                    ),
                }
            elif item.is_substituted:
                message = (
                    f"'{item.canonical_name}' is out of stock. I found '{item.selected_sku.name}' "
                    "as the closest available match. Please confirm it in the checklist."
                )
                response = {"type": "checklist", "message": message, "data": [item]}
            elif not item.selected_sku:
                message = (
                    f"'{item.canonical_name}' is currently out of stock and I couldn't find an "
                    "available substitute."
                )
                response = {"type": "checklist", "message": message, "data": [item]}
            else:
                message = f"I found '{item.selected_sku.name}'. Review it in the checklist before adding it to your cart."
                response = {"type": "checklist", "message": message, "data": [item]}

        elif intent == "RECIPE_EXTRACTION":
            cart = extract_recipe_cart(request.prompt)
            response = {
                "type": "checklist",
                "message": "I prepared these items for review. Select or unselect anything before adding them to your cart.",
                "data": cart,
            }
        else:
            raise HTTPException(status_code=500, detail="Unsupported intent")

        status_code = "200"
        return response
    except HTTPException:
        request_errors.add(1, metric_attributes(route="/api/blinkit-assistant", intent=intent))
        raise
    except Exception:
        request_errors.add(1, metric_attributes(route="/api/blinkit-assistant", intent=intent))
        raise
    finally:
        attributes = metric_attributes(
            route="/api/blinkit-assistant",
            intent=intent,
            status_code=status_code,
        )
        request_duration.record(perf_counter() - started_at, attributes)
        request_count.add(1, attributes)


@app.get("/metrics")
def metrics_endpoint():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/observability/summary")
def observability_summary(window: str = "24h", environment_filter: str | None = None):
    allowed_windows = {"15m", "1h", "24h", "7d"}
    if window not in allowed_windows:
        raise HTTPException(status_code=400, detail=f"window must be one of {sorted(allowed_windows)}")

    selected_environment = environment_filter or environment
    base_selector = f'route="/api/blinkit-assistant",environment="{selected_environment}"'
    intent_metrics = {}
    for intent_name in ["CHAT", "INVENTORY_QUERY", "RECIPE_EXTRACTION", "CATALOG_QUERY"]:
        selector = f'{base_selector},intent="{intent_name}"'
        samples = prometheus_count("blinkit_requests", selector, window)
        errors = prometheus_count("blinkit_request_errors", selector, window)
        intent_metrics[intent_name] = {
            "p50_ms": prometheus_quantile("blinkit_request_duration_seconds", selector, window, 0.50),
            "p95_ms": prometheus_p95("blinkit_request_duration_seconds", selector, window),
            "p99_ms": prometheus_quantile("blinkit_request_duration_seconds", selector, window, 0.99),
            "sample_count": samples,
            "error_count": errors,
            "error_rate_pct": round((errors / samples) * 100, 2) if samples else 0,
        }

    dependency_selector = f'environment="{selected_environment}"'
    metrics_payload = {
        "request_p50_ms": prometheus_quantile("blinkit_request_duration_seconds", base_selector, window, 0.50),
        "request_p95_ms": prometheus_p95("blinkit_request_duration_seconds", base_selector, window),
        "request_p99_ms": prometheus_quantile("blinkit_request_duration_seconds", base_selector, window, 0.99),
        "request_sample_count": prometheus_count("blinkit_requests", base_selector, window),
        "request_error_count": prometheus_count("blinkit_request_errors", base_selector, window),
        "intent_p95_ms": intent_metrics,
        "gemini_p95_ms": prometheus_p95("blinkit_gemini_duration_seconds", dependency_selector, window),
        "huggingface_p95_ms": prometheus_p95("blinkit_huggingface_embedding_duration_seconds", dependency_selector, window),
        "postgresql_p95_ms": prometheus_p95("blinkit_postgresql_query_duration_seconds", dependency_selector, window),
        "database_error_count": prometheus_count("blinkit_database_errors", dependency_selector, window),
    }
    has_data = any(value is not None for value in metrics_payload.values() if not isinstance(value, dict))
    return {
        "status": "ok" if has_data else "unavailable",
        "source": "OpenTelemetry metrics via Prometheus",
        "window": window,
        "environment": selected_environment,
        "route": "POST /api/blinkit-assistant",
        "metrics": metrics_payload,
    }