from __future__ import annotations

from sentence_transformers import SentenceTransformer

from app.config import settings

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    return get_model().encode(texts, show_progress_bar=False).tolist()


def embed_one(text: str) -> list[float]:
    return get_model().encode(text, show_progress_bar=False).tolist()
