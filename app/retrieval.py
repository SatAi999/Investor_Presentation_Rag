from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.config import settings
from app.embedder import embed_one
from app.vector_store import collection_exists, get_client


def retrieve(question: str, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
    """
    Embed the question and search Qdrant for the top_k most similar chunks.

    Returns a list of (chunk_payload, similarity_score) tuples,
    sorted by score descending.
    """
    if not collection_exists():
        return []

    client = get_client()
    query_vector = embed_one(question)

    # qdrant-client >= 1.7.0 uses query_points(); .search() was removed in 1.10+
    response = client.query_points(
        collection_name=settings.collection_name,
        query=query_vector,
        limit=top_k,
        with_payload=True,
        with_vectors=False,
    )

    return [(hit.payload, hit.score) for hit in response.points]
