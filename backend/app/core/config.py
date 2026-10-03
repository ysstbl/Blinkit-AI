import os


class Settings:
    database_url: str | None = os.getenv("DATABASE_URL")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    hf_token: str | None = os.getenv("HF_TOKEN")
    hf_embedding_model: str = os.getenv(
        "HF_EMBEDDING_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2",
    )
    allowed_origins: list[str] = [
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]


settings = Settings()
