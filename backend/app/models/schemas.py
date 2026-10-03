from pydantic import BaseModel


class AssistantRequest(BaseModel):
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


intent_schema = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["INVENTORY_QUERY", "CATALOG_QUERY", "RECIPE_EXTRACTION", "CHAT"],
        },
        "query_type": {
            "type": "string",
            "enum": ["CHEAPEST_ITEM", "MOST_EXPENSIVE_ITEM", "CHAT"],
        },
        "cleaned_query": {
            "type": "string",
            "description": "The core product or recipe query",
        },
    },
    "required": ["intent", "query_type", "cleaned_query"],
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
                    "is_pantry_staple": {"type": "boolean"},
                },
                "required": ["canonical_name", "quantity", "is_pantry_staple"],
            },
        },
    },
    "required": ["dish_name", "ingredients"],
}
