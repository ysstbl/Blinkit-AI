import google.generativeai as genai

from app.core.config import settings
from app.models.schemas import intent_schema, recipe_schema

genai.configure(api_key=settings.gemini_api_key)
llm_model = genai.GenerativeModel("gemini-3.1-flash-lite")


def generate_content(prompt: str, response_schema: dict | None = None):
    kwargs = {}
    if response_schema is not None:
        kwargs["generation_config"] = genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
        )
    return llm_model.generate_content(prompt, **kwargs)
