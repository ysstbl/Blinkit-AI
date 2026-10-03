import json

from fastapi import HTTPException

from app.clients.gemini_client import generate_content
from app.models.schemas import IngredientMatch, recipe_schema
from app.services.catalog_service import search_catalog
from app.services.checklist_service import choose_available_sku


def extract_recipe_cart(prompt: str) -> list[IngredientMatch]:
    localization_prompt = f"""
    Extract the recipe ingredients for: {prompt}.
    IMPORTANT INSTRUCTIONS:
    1. Translate Western ingredient names into standard Indian grocery terms (e.g., 'bell pepper' -> 'capsicum', 'cilantro' -> 'coriander leaves').
    2. CRITICAL: Strip ALL preparation adjectives, measurements, and physical forms. (e.g., 'minced ginger' -> 'ginger', 'sliced onion' -> 'onion').
    3. Keep names strictly to the raw base ingredient unless a processed version is specifically requested.
    4. Be precise with every ingredient (e.g., don't give 'oil', be specific 'mustard oil'/'olive oil').
    """
    response = generate_content(localization_prompt, recipe_schema)
    try:
        parsed_data = json.loads(response.text)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=500, detail="Failed to parse LLM output") from error

    final_cart = []
    for item in parsed_data.get("ingredients", []):
        matches = search_catalog(item["canonical_name"], recipe_context=True)
        selected_sku, is_substituted, original_sku, reason = choose_available_sku(matches)
        final_cart.append(
            IngredientMatch(
                canonical_name=item["canonical_name"],
                quantity=item["quantity"],
                is_pantry_staple=item["is_pantry_staple"],
                selected_sku=selected_sku,
                is_substituted=is_substituted,
                original_sku=original_sku,
                substitution_reason=reason,
                raw_matches=matches,
            )
        )
    return final_cart
