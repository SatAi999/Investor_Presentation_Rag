from __future__ import annotations

from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from app.config import settings

VECTOR_SIZE = 384  # all-MiniLM-L6-v2 output dimensionality

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        path = Path(settings.qdrant_path)
        path.mkdir(parents=True, exist_ok=True)
        _client = QdrantClient(path=str(path))
    return _client


def ensure_collection() -> None:
    client = get_client()
    existing = {c.name for c in client.get_collections().collections}
    if settings.collection_name not in existing:
        client.create_collection(
            collection_name=settings.collection_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def collection_exists() -> bool:
    client = get_client()
    existing = {c.name for c in client.get_collections().collections}
    return settings.collection_name in existing
