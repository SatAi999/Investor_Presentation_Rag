"""
pytest test suite for the Investor Presentation RAG API.

Run with:
    pytest tests/ -v
"""
import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _use_in_memory_qdrant(monkeypatch):
    """
    Replace the Qdrant client singleton with an in-memory instance so tests
    never touch the on-disk qdrant_data/ directory (which may be locked by a
    running server).
    """
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams
    import app.vector_store as vs

    mem_client = QdrantClient(":memory:")
    mem_client.create_collection(
        collection_name="presentation_chunks",
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )
    monkeypatch.setattr(vs, "_client", mem_client)


# ── /health ───────────────────────────────────────────────────────────────────

def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200


def test_health_schema():
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert "ollama_model" in data
    assert "embedding_model" in data
    assert "collection" in data


# ── /ingest ───────────────────────────────────────────────────────────────────

def test_ingest_rejects_non_pdf():
    fake = io.BytesIO(b"this is not a pdf")
    response = client.post(
        "/ingest",
        files={"file": ("notes.txt", fake, "text/plain")},
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_ingest_rejects_empty_filename():
    fake = io.BytesIO(b"%PDF-1.4 fake content")
    response = client.post(
        "/ingest",
        files={"file": ("document.docx", fake, "application/vnd.openxmlformats")},
    )
    assert response.status_code == 400


# ── /query ────────────────────────────────────────────────────────────────────

def test_query_rejects_empty_question():
    response = client.post("/query", json={"question": ""})
    assert response.status_code == 422


def test_query_rejects_top_k_zero():
    response = client.post("/query", json={"question": "What is revenue?", "top_k": 0})
    assert response.status_code == 422


def test_query_rejects_top_k_too_large():
    response = client.post("/query", json={"question": "What is revenue?", "top_k": 21})
    assert response.status_code == 422


def test_query_returns_valid_schema_without_ingested_data():
    """
    When no PDF has been ingested, query should still return a valid
    QueryResponse schema (not a 500 error).
    """
    response = client.post("/query", json={"question": "What is the revenue?", "top_k": 3})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert isinstance(data["citations"], list)
    assert "retrieval" in data
    assert "top_k" in data["retrieval"]
    assert "chunks_consulted" in data["retrieval"]
    assert isinstance(data["limitations"], list)


def test_query_default_top_k():
    """top_k should default to 5 if not specified."""
    response = client.post("/query", json={"question": "What are the growth priorities?"})
    assert response.status_code == 200
    data = response.json()
    assert data["retrieval"]["top_k"] == 5
