"""
RAG Evaluation Pipeline — 4-Metric, Document-Agnostic
======================================================
Works with ANY ingested investor presentation PDF. No hardcoded questions,
page numbers, or document-specific ground truth.

Metrics (all 0.0–1.0):
  1. context_relevance  — Are retrieved chunks relevant to the question?
                          (avg Qdrant cosine score across top_k chunks)
  2. faithfulness       — Does the answer stay within the retrieved context?
                          (llama2-as-judge: hallucination check)
  3. answer_relevance   — Does the answer address the question?
                          (cosine similarity: question ↔ answer embedding)
  4. answer_grounding   — Is the answer grounded in the retrieved context?
                          (cosine similarity: answer ↔ context embedding)
                          For the evidence challenge: refusal detection.

Why NOT retrieval_precision:
  It requires hardcoded expected page numbers per question — not portable
  across different PDFs. Dropped in favour of answer_grounding which
  measures the same underlying concern (answer tied to retrieved evidence)
  without any document-specific knowledge.

After baseline, auto-improves settings and re-runs (Round 2).
Winner is selected by mean average score and saved to eval_metrics.json.

Usage:
    python evaluation/auto_improve.py
"""
from __future__ import annotations

import json
import re
import urllib.request

import numpy as np
import requests

API_BASE = "http://localhost:8000"

# ── Evaluation questions — generic, work for any investor presentation ────────
# These describe the TYPE of information to find, not document-specific facts.
# The retriever has to work to surface the right evidence — no circular scoring.
EVAL_SET = [
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

# ── Prompts ───────────────────────────────────────────────────────────────────
PROMPT_STANDARD = """\
You are a financial analyst assistant. Answer ONLY using the context below.
If the context lacks clear information, say: "The presentation does not clearly address this."
Keep answer under 200 words.

CONTEXT:
{context}

QUESTION: {question}

ANSWER:"""

PROMPT_ASSERTIVE = """\
You are a financial analyst. Extract and report any relevant numbers, names, or
facts present in the context — even from tables or chart descriptions.
Only say "The presentation does not clearly address this." if the context truly
contains NO relevant information at all.
Keep answer under 200 words.

CONTEXT:
{context}

QUESTION: {question}

ANSWER:"""

FAITHFULNESS_JUDGE_PROMPT = """\
You are an evaluator. Given a CONTEXT and an ANSWER, determine if every factual
claim in the ANSWER is supported by the CONTEXT.

CONTEXT:
{context}

ANSWER:
{answer}

Reply with ONLY a number between 0.0 and 1.0:
  1.0 = every claim in the answer is supported by the context
  0.5 = some claims are supported, others are not
  0.0 = the answer contains claims not present in the context (hallucination)

SCORE:"""


# ── Core helpers ──────────────────────────────────────────────────────────────

def _build_context(chunks: list[dict]) -> str:
    parts = []
    for c in chunks:
        page = c.get("page_number", "?")
        title = c.get("section_title", "")
        parts.append(f"[Page {page} — {title}]\n{c.get('text', '')}")
    return "\n\n---\n\n".join(parts)


def _call_ollama(prompt: str, model: str = "llama2") -> str:
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode()).get("response", "").strip()


def _embed(texts: list[str]) -> np.ndarray:
    from app.embedder import get_model
    return get_model().encode(texts, show_progress_bar=False)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a.flatten(), b.flatten()
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom else 0.0


def _retrieve(question: str, top_k: int) -> tuple[list[dict], list[float]]:
    from app.config import settings
    from app.embedder import embed_one
    from app.vector_store import get_client

    client = get_client()
    vector = embed_one(question)
    response = client.query_points(
        collection_name=settings.collection_name,
        query=vector,
        limit=top_k,
        with_payload=True,
        with_vectors=False,
    )
    return [h.payload for h in response.points], [h.score for h in response.points]


# ── Metrics ───────────────────────────────────────────────────────────────────

def metric_context_relevance(scores: list[float]) -> float:
    """Average Qdrant cosine similarity across retrieved chunks."""
    return float(np.mean(scores)) if scores else 0.0


def metric_faithfulness(answer: str, chunks: list[dict]) -> float:
    """llama2-as-judge: does the answer stay within the retrieved context?"""
    if not chunks:
        return 1.0
    context = _build_context(chunks[:3])[:2000]
    prompt = FAITHFULNESS_JUDGE_PROMPT.format(context=context, answer=answer[:500])
    raw = _call_ollama(prompt)
    match = re.search(r"\b([01](?:\.\d+)?)\b", raw)
    return float(match.group(1)) if match else 0.5


def metric_answer_relevance(question: str, answer: str) -> float:
    """Cosine similarity between question embedding and answer embedding."""
    vecs = _embed([question, answer])
    return _cosine(vecs[0], vecs[1])


def metric_answer_grounding(answer: str, chunks: list[dict], is_evidence_challenge: bool) -> float:
    """
    For normal questions: cosine similarity between answer and the
    concatenated retrieved context. High score = answer uses language and
    facts from the evidence. No document-specific knowledge needed.

    For the evidence challenge: refusal detection — score 1.0 if the
    system correctly says it doesn't know, 0.0 if it hallucinated an answer.
    """
    if is_evidence_challenge:
        lower = answer.lower()
        return 1.0 if any(p in lower for p in [
            "does not clearly address", "not provide", "no information",
            "cannot", "not mentioned", "not available",
        ]) else 0.0

    if not chunks:
        return 0.0

    context_text = " ".join(c.get("text", "") for c in chunks)[:2000]
    vecs = _embed([answer, context_text])
    return max(0.0, _cosine(vecs[0], vecs[1]))


# ── Round runner ──────────────────────────────────────────────────────────────

METRIC_KEYS = ["context_relevance", "faithfulness", "answer_relevance", "answer_grounding"]

def run_round(label: str, top_k: int, prompt_template: str, threshold: float) -> list[dict]:
    print(f"\n{'─'*68}")
    print(f"  ROUND: {label}  |  top_k={top_k}  |  threshold={threshold}")
    print(f"{'─'*68}")
    print(f"  {'Q#':<4} {'Type':<22} {'CR':>6} {'FF':>6} {'AR':>6} {'AG':>6} {'AVG':>6}")
    print(f"  {'─'*58}")

    results = []
    for i, item in enumerate(EVAL_SET, 1):
        question = item["question"]
        is_challenge = item["type"] == "Evidence challenge"

        chunks, scores = _retrieve(question, top_k)
        top_score = scores[0] if scores else 0.0
        limitations = []
        if top_score < threshold:
            limitations.append(f"Weak retrieval: top score={top_score:.3f}")

        if chunks:
            context = _build_context(chunks)
            answer = _call_ollama(prompt_template.format(context=context, question=question))
        else:
            answer = "The presentation does not clearly address this."

        cr  = metric_context_relevance(scores)
        ff  = metric_faithfulness(answer, chunks)
        ar  = metric_answer_relevance(question, answer)
        ag  = metric_answer_grounding(answer, chunks, is_challenge)
        avg = float(np.mean([cr, ff, ar, ag]))

        print(f"  Q{i:<3} {item['type']:<22} {cr:>6.2f} {ff:>6.2f} {ar:>6.2f} {ag:>6.2f} {avg:>6.2f}")

        results.append({
            "type": item["type"],
            "question": question,
            "answer": answer,
            "pages_retrieved": sorted({str(c.get("page_number")) for c in chunks}),
            "metrics": {
                "context_relevance": round(cr,  4),
                "faithfulness":      round(ff,  4),
                "answer_relevance":  round(ar,  4),
                "answer_grounding":  round(ag,  4),
                "average":           round(avg, 4),
            },
            "limitations": limitations,
            "top_k_used": top_k,
        })

    mean = {
        m: round(float(np.mean([r["metrics"][m] for r in results])), 4)
        for m in METRIC_KEYS + ["average"]
    }
    print(f"  {'─'*58}")
    print(f"  {'MEAN':<26} {mean['context_relevance']:>6.2f} {mean['faithfulness']:>6.2f} "
          f"{mean['answer_relevance']:>6.2f} {mean['answer_grounding']:>6.2f} {mean['average']:>6.2f}")
    return results


# ── Auto-improvement logic ────────────────────────────────────────────────────

def diagnose_and_improve(baseline: list[dict]) -> dict:
    low_cr = [r for r in baseline if r["metrics"]["context_relevance"] < 0.50]
    low_ff = [r for r in baseline if r["metrics"]["faithfulness"] < 0.50]
    low_ag = [r for r in baseline if r["metrics"]["answer_grounding"] < 0.40
              and r["type"] != "Evidence challenge"]

    new_top_k = 5
    prompt = PROMPT_STANDARD
    threshold = 0.30

    print(f"\n  DIAGNOSIS")
    print(f"  ├── Low context relevance (<0.50): {len(low_cr)} questions → fix: raise top_k")
    print(f"  ├── Low faithfulness      (<0.50): {len(low_ff)} questions → fix: assertive prompt")
    print(f"  └── Low answer grounding  (<0.40): {len(low_ag)} questions → fix: assertive prompt")

    if len(low_cr) > 1:
        new_top_k = min(10, 5 + len(low_cr))
        threshold = 0.20
        print(f"\n  FIX ▶ top_k: 5 → {new_top_k}")
        print(f"  FIX ▶ similarity_threshold: 0.30 → {threshold}")

    if len(low_ag) > 1 or len(low_ff) > 1:
        prompt = PROMPT_ASSERTIVE
        print(f"  FIX ▶ prompt: STANDARD → ASSERTIVE")

    return {"top_k": new_top_k, "prompt": prompt, "threshold": threshold}


# ── Comparison table ──────────────────────────────────────────────────────────

def compare(baseline: list[dict], improved: list[dict]) -> None:
    print(f"\n{'='*68}")
    print("  BEFORE vs AFTER — MEAN SCORES")
    print(f"{'='*68}")
    print(f"  {'Metric':<25} {'Before':>8} {'After':>8} {'Δ':>8}")
    print(f"  {'─'*52}")

    for m in METRIC_KEYS + ["average"]:
        before = float(np.mean([r["metrics"][m] for r in baseline]))
        after  = float(np.mean([r["metrics"][m] for r in improved]))
        delta  = after - before
        arrow  = "↑" if delta > 0.01 else ("↓" if delta < -0.01 else "→")
        print(f"  {m:<25} {before:>8.3f} {after:>8.3f} {arrow}{abs(delta):>6.3f}")

    print(f"{'='*68}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    try:
        h = requests.get(f"{API_BASE}/health", timeout=5)
        h.raise_for_status()
        info = h.json()
    except Exception as exc:
        print(f"ERROR: Cannot reach API — {exc}\nStart it with: uvicorn app.main:app --reload")
        return

    print(f"{'='*68}")
    print("  RAG EVALUATION PIPELINE  (4-metric, document-agnostic)")
    print(f"{'='*68}")
    print(f"  Model : {info['ollama_model']}  |  Embed : {info['embedding_model']}")
    print(f"\n  Metrics:")
    print(f"    CR  context_relevance  — avg cosine(question, retrieved chunks)")
    print(f"    FF  faithfulness       — llama2-as-judge (hallucination check)")
    print(f"    AR  answer_relevance   — cosine(question, answer)")
    print(f"    AG  answer_grounding   — cosine(answer, context); refusal check for Q6")
    print(f"\n  Questions: {len(EVAL_SET)} generic types — work for any investor presentation\n")

    # Round 1: baseline
    baseline = run_round("BASELINE", top_k=5, prompt_template=PROMPT_STANDARD, threshold=0.30)

    # Diagnose & auto-improve
    improvements = diagnose_and_improve(baseline)

    # Round 2: improved
    improved = run_round(
        "IMPROVED",
        top_k=improvements["top_k"],
        prompt_template=improvements["prompt"],
        threshold=improvements["threshold"],
    )

    compare(baseline, improved)

    # ── Pick winner by mean average score ─────────────────────────────────────
    baseline_avg = float(np.mean([r["metrics"]["average"] for r in baseline]))
    improved_avg = float(np.mean([r["metrics"]["average"] for r in improved]))

    if baseline_avg >= improved_avg:
        winner_label    = "baseline"
        winner_settings = {"top_k": 5, "threshold": 0.30, "prompt": "standard"}
    else:
        winner_label    = "improved"
        winner_settings = {
            "top_k": improvements["top_k"],
            "threshold": improvements["threshold"],
            "prompt": "assertive" if improvements["prompt"] == PROMPT_ASSERTIVE else "standard",
        }

    print(f"  WINNER: {winner_label.upper()}  "
          f"(baseline avg={baseline_avg:.3f}  improved avg={improved_avg:.3f})")
    print(f"  Sticking with: top_k={winner_settings['top_k']}  "
          f"threshold={winner_settings['threshold']}  "
          f"prompt={winner_settings['prompt']}\n")

    # Save full output
    output = {
        "baseline": {
            "settings": {"top_k": 5, "threshold": 0.30, "prompt": "standard"},
            "mean_scores": {
                m: round(float(np.mean([r["metrics"][m] for r in baseline])), 4)
                for m in METRIC_KEYS + ["average"]
            },
            "results": baseline,
        },
        "improved": {
            "settings": {
                "top_k": improvements["top_k"],
                "threshold": improvements["threshold"],
                "prompt": "assertive" if improvements["prompt"] == PROMPT_ASSERTIVE else "standard",
            },
            "mean_scores": {
                m: round(float(np.mean([r["metrics"][m] for r in improved])), 4)
                for m in METRIC_KEYS + ["average"]
            },
            "results": improved,
        },
        "winner": {
            "round": winner_label,
            "settings": winner_settings,
            "mean_average": round(max(baseline_avg, improved_avg), 4),
        },
    }

    out_path = "evaluation/eval_metrics.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  Full results saved → {out_path}")
    print(f"  Recommended .env:  TOP_K={winner_settings['top_k']}  "
          f"SIMILARITY_THRESHOLD={winner_settings['threshold']}\n")


if __name__ == "__main__":
    main()
