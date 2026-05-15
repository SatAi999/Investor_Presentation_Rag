"""
Evaluation report: runs 6 analyst-style questions against the live RAG system
and prints a structured report.

Questions are GENERIC by design — they describe the type of information to
find, not document-specific facts. They work for any investor presentation PDF.

Usage:
    1. Start the API:  uvicorn app.main:app --reload
    2. Ingest the PDF: use the React UI, Streamlit UI, or POST /ingest directly
    3. Run this script: python evaluation/eval_report.py
"""
from __future__ import annotations

import json
import sys

import requests

API_BASE = "http://localhost:8000"
TOP_K = 5

# 6 question types from the assignment spec.
# Generic phrasing means they work for ANY investor presentation — no hardcoding.
QUESTIONS = [
    {
        "type": "Factual lookup",
        "question": "What is the latest revenue figure or total sales number reported in this presentation, and for which period?",
    },
    {
        "type": "Business segment",
        "question": "Which business segment, brand, or product category contributed most to the company's revenue or growth?",
    },
    {
        "type": "Strategy",
        "question": "What are the key strategic priorities or growth initiatives that management has outlined in this presentation?",
    },
    {
        "type": "Risk / challenge",
        "question": "What business risks, market headwinds, or operational challenges are disclosed in this presentation?",
    },
    {
        "type": "Financial trend",
        "question": "How has the company's revenue or profitability changed across the periods shown in this presentation?",
    },
    {
        "type": "Evidence challenge",
        "question": "What is the company's exact customer acquisition cost per region and its five-year market share projection by country?",
    },
]


def _support_level(answer: str, limitations: list[str]) -> str:
    lower = answer.lower()
    if "does not clearly address" in lower or "not clearly" in lower:
        return "Unsupported"
    if limitations:
        return "Partially supported"
    return "Supported"


def run_evaluation() -> None:
    print("=" * 72)
    print("  INVESTOR PRESENTATION RAG — EVALUATION REPORT")
    print("=" * 72)

    try:
        h = requests.get(f"{API_BASE}/health", timeout=5)
        h.raise_for_status()
        info = h.json()
        print(f"  API     : OK")
        print(f"  Model   : {info['ollama_model']}")
        print(f"  Embed   : {info['embedding_model']}")
        print()
    except Exception as exc:
        print(f"ERROR: Cannot reach API at {API_BASE}.\nStart it with: uvicorn app.main:app\n{exc}")
        sys.exit(1)

    results = []

    for i, q in enumerate(QUESTIONS, 1):
        print(f"Q{i}  [{q['type']}]")
        print(f"    Question : {q['question']}")

        try:
            resp = requests.post(
                f"{API_BASE}/query",
                json={"question": q["question"], "top_k": TOP_K},
                timeout=180,
            )
            resp.raise_for_status()
        except Exception as exc:
            print(f"    ERROR    : {exc}\n")
            continue

        data = resp.json()
        answer = data["answer"]
        citations = data["citations"]
        limitations = data["limitations"]
        pages = sorted({str(c["page"]) for c in citations})
        support = _support_level(answer, limitations)

        display_answer = answer[:350] + ("..." if len(answer) > 350 else "")

        print(f"    Answer   : {display_answer}")
        print(f"    Pages    : {', '.join(pages) if pages else 'None'}")
        print(f"    Support  : {support}")
        if limitations:
            print(f"    Note     : {limitations[0]}")
        print()

        results.append({
            "type": q["type"],
            "question": q["question"],
            "answer": answer,
            "pages_cited": pages,
            "support": support,
            "limitations": limitations,
        })

    out_path = "evaluation/eval_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("=" * 72)
    print(f"  Full results saved to {out_path}")
    print("=" * 72)


if __name__ == "__main__":
    run_evaluation()
