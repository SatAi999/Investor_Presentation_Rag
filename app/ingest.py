from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone

import pdfplumber
from qdrant_client.models import PointStruct

from app.config import settings
from app.embedder import embed_texts
from app.vector_store import ensure_collection, get_client


def _make_chunk_id(doc_name: str, page_number: int) -> str:
    """Generate a stable UUID chunk ID from doc name + page number."""
    raw = f"{doc_name}_page_{page_number}"
    md5_hex = hashlib.md5(raw.encode()).hexdigest()
    return str(uuid.UUID(md5_hex))


def _extract_section_title(text: str) -> str:
    """Use first non-empty line as best-effort slide/section title."""
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped:
            return stripped[:100]
    return "Unknown"


def _clean_text(text: str) -> str:
    if not text:
        return ""
    # Collapse multiple spaces/tabs but preserve newlines for structure
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def ingest_pdf(pdf_path: str, doc_name: str) -> int:
    """
    Parse PDF page by page, create one chunk per page, embed, and upsert to Qdrant.

    Strategy: page-level chunking (one chunk = one slide/page).
    This preserves slide context and naturally maps citations to page numbers.
    """
    ensure_collection()
    client = get_client()

    chunks: list[dict] = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_number = i + 1
            raw_text = page.extract_text() or ""
            text = _clean_text(raw_text)
            if not text:
                continue

            chunk_id = _make_chunk_id(doc_name, page_number)
            section_title = _extract_section_title(raw_text)

            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "text": text,
                    "page_number": page_number,
                    "section_title": section_title,
                    "metadata": {
                        "company": doc_name,
                        "document_name": doc_name,
                        "ingestion_timestamp": datetime.now(timezone.utc).isoformat(),
                        "page_number": page_number,
                        "section_title": section_title,
                    },
                }
            )

    if not chunks:
        return 0

    texts = [c["text"] for c in chunks]
    vectors = embed_texts(texts)

    points = [
        PointStruct(id=c["chunk_id"], vector=v, payload=c)
        for c, v in zip(chunks, vectors)
    ]

    client.upsert(collection_name=settings.collection_name, points=points)
    return len(chunks)
