from app.models.schemas import IngredientMatch, MatchedSKU
from app.services.catalog_service import search_catalog


def choose_available_sku(matches: list[MatchedSKU]):
    if not matches:
        return None, False, None, None

    primary_match = matches[0]
    if primary_match.in_stock:
        return primary_match, False, None, None

    for fallback in matches[1:]:
        if fallback.in_stock:
            return (
                fallback,
                True,
                primary_match,
                "The closest catalog match is out of stock.",
            )
    return None, False, primary_match, None


def create_product_checklist(query: str) -> IngredientMatch | None:
    matches = search_catalog(query)
    if not matches:
        return None

    selected_sku, is_substituted, original_sku, reason = choose_available_sku(matches)
    return IngredientMatch(
        canonical_name=query,
        quantity="1",
        is_pantry_staple=False,
        selected_sku=selected_sku,
        is_substituted=is_substituted,
        original_sku=original_sku,
        substitution_reason=reason,
        raw_matches=matches,
    )
