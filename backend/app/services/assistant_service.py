from app.clients.gemini_client import generate_content
from app.services.catalog_service import answer_catalog_query, extract_catalog_filter
from app.services.checklist_service import create_product_checklist
from app.services.intent_service import classify_intent
from app.services.recipe_service import extract_recipe_cart


class AssistantService:
    def handle(self, prompt: str):
        routing = classify_intent(prompt)
        intent = routing.get("intent")
        query_type = routing.get("query_type", "CHAT")
        query = routing.get("cleaned_query")

        if intent == "CATALOG_QUERY":
            catalog_filter = extract_catalog_filter(prompt, query)
            return {
                "type": "chat",
                "message": answer_catalog_query(query_type, catalog_filter),
            }

        if intent == "CHAT":
            response = generate_content(
                f"Reply naturally and briefly to this grocery assistant message: '{prompt}'. "
                "Do not claim to have searched the catalog or changed the cart.",
            )
            return {"type": "chat", "message": response.text.strip()}

        if intent == "INVENTORY_QUERY":
            return self._inventory_response(query)

        if intent == "RECIPE_EXTRACTION":
            return {
                "type": "checklist",
                "message": (
                    "I prepared these items for review. Select or unselect anything "
                    "before adding them to your cart."
                ),
                "data": extract_recipe_cart(prompt),
            }

        raise ValueError("Unsupported intent")

    @staticmethod
    def _inventory_response(query: str):
        item = create_product_checklist(query)
        if not item:
            return {
                "type": "chat",
                "message": (
                    f"I couldn't find '{query}' in the catalog, so I haven't added "
                    "anything to the checklist."
                ),
            }
        if item.is_substituted:
            return {
                "type": "checklist",
                "message": (
                    f"'{item.canonical_name}' is out of stock. I found "
                    f"'{item.selected_sku.name}' as the closest available match. "
                    "Please confirm it in the checklist."
                ),
                "data": [item],
            }
        if not item.selected_sku:
            return {
                "type": "checklist",
                "message": (
                    f"'{item.canonical_name}' is currently out of stock and I "
                    "couldn't find an available substitute."
                ),
                "data": [item],
            }
        return {
            "type": "checklist",
            "message": (
                f"I found '{item.selected_sku.name}'. Review it in the checklist "
                "before adding it to your cart."
            ),
            "data": [item],
        }


assistant_service = AssistantService()
