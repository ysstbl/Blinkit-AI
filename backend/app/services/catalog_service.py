import re

from app.clients.embeddings_client import create_embedding
from app.models.schemas import MatchedSKU
from app.repositories.catalog_repository import find_price_extreme, search_by_embedding

NON_FOOD_FLAGS = {
    "bleach", "bathroom", "cleaner", "cleaning", "disinfectant", "dishwash",
    "drain", "fabric", "floor", "handwash", "laundry", "phenyl", "polish",
    "sanitizer", "shampoo", "soap", "toilet", "surface", "detergent",
}
FOOD_CATEGORY_FLAGS = {
    "bakery", "beverage", "dairy", "food", "fruit", "grocery", "meat",
    "produce", "snack", "spice", "staple", "vegetable",
}
PROCESSED_FLAGS = {
    "pickle", "paste", "sauce", "powder", "puree", "crushed", "juice",
    "extract", "syrup", "frozen", "spread", "dip", "dressing", "mayo",
    "chips", "snack", "ready", "mix", "masala", "ketchup", "soup", "cake",
    "butter",
}
FRESH_BOOST_FLAGS = {"fresho", "fresh", "organic", "raw", "whole"}


def _is_food_candidate(row) -> bool:
    product_text = f"{row[1]} {row[5] or ''}".lower()
    return not any(flag in product_text for flag in NON_FOOD_FLAGS)


def _calculate_relevance(row, query_terms: set[str], normalized_query: str) -> float:
    name = row[1].lower()
    name_terms = set(name.replace("-", " ").split())
    overlap = sum(
        1
        for query_term in query_terms
        if any(query_term in name_term or name_term in query_term for name_term in name_terms)
    )
    has_processed_flag = any(flag in name_terms for flag in PROCESSED_FLAGS)
    wants_processed = any(flag in query_terms for flag in PROCESSED_FLAGS)
    has_fresh_flag = any(flag in name_terms for flag in FRESH_BOOST_FLAGS)
    processed_penalty = 8.0 if has_processed_flag and not wants_processed else 0.0
    processed_boost = 4.0 if has_processed_flag and wants_processed else 0.0
    fresh_boost = 3.0 if has_fresh_flag and not wants_processed else 0.0
    length_penalty = (len(name_terms) - overlap) * 0.1
    exact_phrase_boost = 5.0 if normalized_query in name else 0.0
    food_category_boost = 1.5 if any(
        flag in (row[5] or "").lower() for flag in FOOD_CATEGORY_FLAGS
    ) else 0.0
    return (
        overlap
        + exact_phrase_boost
        + food_category_boost
        + fresh_boost
        + processed_boost
        - processed_penalty
        - length_penalty
    )


def search_catalog(ingredient_name: str, recipe_context: bool = False) -> list[MatchedSKU]:
    vector = create_embedding(f"Product: {ingredient_name}")
    results = search_by_embedding(vector)
    query_terms = set(ingredient_name.lower().split())
    normalized_query = re.sub(r"[^a-z0-9 ]", " ", ingredient_name.lower())

    if recipe_context:
        results = [row for row in results if _is_food_candidate(row)]
    results.sort(
        key=lambda row: _calculate_relevance(row, query_terms, normalized_query),
        reverse=True,
    )
    if not results or _calculate_relevance(results[0], query_terms, normalized_query) <= 0:
        return []

    return [
        MatchedSKU(
            sku_id=row[0],
            name=row[1],
            price=row[2],
            in_stock=row[3],
            pack_size=row[4],
        )
        for row in results[:15]
    ]


def extract_catalog_filter(prompt: str, cleaned_query: str | None) -> str:
    source = cleaned_query or prompt
    source = re.sub(
        r"\b(cheapest|most expensive|lowest price|highest price|price|item|items|"
        r"product|products|in stock|available|is|are|the|what|whats|what's|please|"
        r"show|me|find)\b",
        " ",
        source.lower(),
    )
    return " ".join(source.split())


def answer_catalog_query(query_type: str, catalog_filter: str = "") -> str:
    order = "ASC" if query_type == "CHEAPEST_ITEM" else "DESC"
    label = "cheapest" if query_type == "CHEAPEST_ITEM" else "most expensive"
    filter_terms = [term for term in catalog_filter.lower().split() if len(term) > 1]
    result = find_price_extreme(order, filter_terms)
    if not result:
        scope = f" matching '{catalog_filter}'" if filter_terms else ""
        return f"I couldn't find an in-stock item{scope} to identify as the {label} item right now."

    name, price, pack_size = result
    scope = f" {catalog_filter}" if filter_terms else ""
    return f"The {label}{scope} in-stock item is {name} at ₹{price} for {pack_size}."
