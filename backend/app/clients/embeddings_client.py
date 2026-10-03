from huggingface_hub import InferenceClient

from app.core.config import settings

embedding_client = InferenceClient(token=settings.hf_token)
embedding_model = settings.hf_embedding_model


def create_embedding(text: str) -> list[float]:
    embedding = embedding_client.feature_extraction(text, model=embedding_model)
    return embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
