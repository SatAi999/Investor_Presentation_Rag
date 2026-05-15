from __future__ import annotations

import json
import urllib.request
from typing import Any, Dict, List, Tuple

from app.config import settings
from app.models import Citation, QueryResponse, RetrievalInfo

_PROMPT = """\
You are a financial analyst assistant. Your job is to answer questions about an investor presentation.

RULES:
1. Answer ONLY using the context provided below. Do not use outside knowledge.
2. If the context does not contain enough information, respond with exactly:
   "The presentation does not clearly address this."
3. Be specific — mention figures, names, and facts from the context when available.
4. Keep the answer under 200 words.

CONTEXT:
{context}

QUESTION: {question}

ANSWER:"""


def _build_context(chunks_with_scores: List[Tuple[Dict[str, Any], float]]) -> str:
    parts = []
    for chunk, score in chunks_with_scores:
        page = chunk.get("page_number", "?")
        title = chunk.get("section_title", "")
        text = chunk.get("text", "")
        parts.append(f"[Page {page} — {title}]\n{text}")
    return "\n\n---\n\n".join(parts)


def _call_ollama(prompt: str) -> str:
    payload = json.dumps(
        {"model": settings.ollama_model, "prompt": prompt, "stream": False}
    ).encode()
    req = urllib.request.Request(
        f"{settings.ollama_base_url}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode())
            return data.get("response", "").strip()
    except OSError as exc:
        raise RuntimeError(
            f"Cannot reach Ollama at {settings.ollama_base_url}. "
            "Ensure it is running: open a terminal and run `ollama serve`."
        ) from exc


def _excerpt(text: str, max_len: int = 150) -> str:
    text = text.strip()
    return (text[:max_len] + "...") if len(text) > max_len else text


def generate_answer(
    question: str,
    chunks_with_scores: List[Tuple[Dict[str, Any], float]],
    top_k: int = 5,
) -> QueryResponse:
    limitations: list[str] = []

    if not chunks_with_scores:
        return QueryResponse(
            answer="No relevant content found. Please ingest the presentation PDF first.",
            citations=[],
            retrieval=RetrievalInfo(top_k=top_k, chunks_consulted=0),
            limitations=["Collection is empty — PDF not yet ingested."],
        )

    top_score = chunks_with_scores[0][1]
    if top_score < settings.similarity_threshold:
        limitations.append(
            f"Weak evidence: top similarity score is {top_score:.2f} "
            f"(threshold: {settings.similarity_threshold}). "
            "Answer may not be well-grounded in the presentation."
        )

    context = _build_context(chunks_with_scores)
    prompt = _PROMPT.format(context=context, question=question)
    answer = _call_ollama(prompt)

    seen: set[int] = set()
    citations: list[Citation] = []
    for chunk, _ in chunks_with_scores:
        page = chunk.get("page_number", 0)
        if page in seen:
            continue
        seen.add(page)
        citations.append(
            Citation(
                page=page,
                chunk_id=chunk.get("chunk_id", ""),
                excerpt=_excerpt(chunk.get("text", "")),
            )
        )

    return QueryResponse(
        answer=answer,
        citations=citations,
        retrieval=RetrievalInfo(top_k=top_k, chunks_consulted=len(chunks_with_scores)),
        limitations=limitations,
    )
