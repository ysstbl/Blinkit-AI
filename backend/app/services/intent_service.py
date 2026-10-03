import json

from fastapi import HTTPException

from app.clients.gemini_client import generate_content
from app.models.schemas import intent_schema


def classify_intent(prompt: str) -> dict:
    router_prompt = f"""
    Classify this grocery assistant message: '{prompt}'
    Use RECIPE_EXTRACTION when the user asks what to buy for a dish or recipe.
    Use INVENTORY_QUERY when the user is asking for a specific product or wants to add a product.
    Use CATALOG_QUERY for questions about the catalog as a whole, such as cheapest, most expensive,
    or price comparisons. Use CHAT for general conversation that needs no catalog lookup.
    For CATALOG_QUERY, set query_type to CHEAPEST_ITEM or MOST_EXPENSIVE_ITEM.
    For other intents, set query_type to CHAT and cleaned_query to the product or topic.
    """
    response = generate_content(router_prompt, intent_schema)
    try:
        routing = json.loads(response.text)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=500, detail="Failed to parse intent") from error

    normalized_prompt = prompt.lower()
    if "cheapest" in normalized_prompt or "lowest price" in normalized_prompt:
        routing["intent"] = "CATALOG_QUERY"
        routing["query_type"] = "CHEAPEST_ITEM"
    elif "most expensive" in normalized_prompt or "highest price" in normalized_prompt:
        routing["intent"] = "CATALOG_QUERY"
        routing["query_type"] = "MOST_EXPENSIVE_ITEM"
    return routing
