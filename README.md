# Investor Presentation RAG

Question-answering system over investor presentation PDFs with page-level citations.

---

## Quick Start

```bash
# 1. Activate environment
cd C:\AI_Projects\GenAi_Projects
.\genai_env\Scripts\Activate.ps1

# 2. Install dependencies
cd presentation_rag
pip install -r requirements.txt

# 3. Copy environment config
copy .env.example .env

# 4. Make sure Ollama is running
ollama serve   # (usually auto-starts on Windows)

# 5. Start the API
uvicorn app.main:app --reload
```

API available at: http://localhost:8000  
Swagger docs at: http://localhost:8000/docs

---

## React Frontend

Full-featured React/Vite frontend with dual-role login (user chat + admin dashboard).

```bash
# In a second terminal (Node.js 18+ required)
cd presentation_rag/frontend
npm install
npm run dev
```

App available at: http://localhost:5173

| Username | Password | Role |
|----------|----------|------|
| `user`   | `user123` | User — chat interface |
| `admin`  | `admin123` | Admin — dashboard + user view toggle |

Admin dashboard includes: PDF upload, evaluation pipeline runner, metric charts
(radar + bar), per-question drilldown, Qdrant collection stats, and a toggle
to switch to the User View without logging out.

---

## Streamlit UI (Alternative)

```bash
# Simpler single-page UI — no Node.js required
streamlit run streamlit_app.py
```

Streamlit UI at: http://localhost:8501

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | System status |
| POST | `/ingest` | Upload and index a PDF |
| POST | `/query` | Ask a question, get answer + citations |

POST /ingest expects `multipart/form-data` with a `file` field (PDF only).

POST /query expects JSON:
```json
{ "question": "What was revenue in the latest period?", "top_k": 5 }
```

Response shape:
```json
{
  "answer": "...",
  "citations": [
    { "page": 12, "chunk_id": "...", "excerpt": "..." }
  ],
  "retrieval": { "top_k": 5, "chunks_consulted": 5 },
  "limitations": ["..."]
}
```

---

## Run Tests

```bash
pytest tests/ -v
```

---

## Evaluation and Auto-Improvement

The system has a 2-round evaluation pipeline (`evaluation/auto_improve.py`) that
measures RAG quality, tries to improve the configuration automatically, and saves
the winning settings to `eval_metrics.json`. The admin dashboard reads this file
to display metric charts and the active config.

To run it manually:
```bash
# Requires the API to be running and a PDF already ingested
python evaluation/auto_improve.py
```

It can also be triggered from the admin dashboard using the "Run Evaluation" button,
which streams the output live to the browser via Server-Sent Events.

The pipeline uses 4 metrics:

- Context Relevance: average cosine similarity between the question vector and
  the retrieved chunk vectors. Measures whether retrieval is pulling relevant pages.

- Faithfulness: llama2-as-judge. The model is given the retrieved context and
  the generated answer and asked to score (0 / 0.5 / 1.0) whether the answer's
  claims are actually supported by that context. Catches hallucinated facts.

- Answer Relevance: cosine similarity between the question embedding and the
  answer embedding. Detects answers that are grammatically correct but off-topic.

- Answer Grounding: for regular questions, cosine similarity between the answer
  and the full retrieved context text. For the evidence-challenge question (Q6),
  switches to keyword detection — checks whether the system correctly refused
  rather than making something up.

How the two rounds work:

Round 1 (Baseline) runs all 6 evaluation questions with top_k=5 and the standard
prompt. After that, the script diagnoses the results: if more than one question
had low context relevance, top_k is raised (up to 10). If faithfulness or grounding
was low, it switches to an assertive prompt that pushes the model to extract more
from partial evidence. Round 2 (Improved) reruns with those adjusted settings.
Whichever round had the higher average score across all 4 metrics is saved as the
winner. The winning top_k and prompt type are what the system uses going forward.

The 6 evaluation questions cover: a factual number lookup, a business segment
comparison, strategic priorities, risks and challenges, a multi-period financial
trend, and one intentional evidence-challenge question (asking for a metric that
doesn't exist in any typical investor presentation) to verify the system refuses
correctly instead of hallucinating an answer.

A simpler evaluation report that just calls the live API and records support levels
is also available:
```bash
python evaluation/eval_report.py
```

---

## Engineering Decisions

### 1. PDF Parser — pdfplumber

pdfplumber preserves page boundaries natively and returns per-page objects directly,
making page-number attribution trivial with no post-hoc alignment needed. It extracts
text with reasonable layout fidelity for structured slide decks.

Where it fails:
- Scanned/image-only PDFs return empty text (no OCR).
- Heavily formatted slides with overlapping text boxes may merge content out of order.
- Multi-column layouts can interleave columns incorrectly.
- Tables are extracted as flat text, losing row/column structure.

For production, a fallback to PyMuPDF for layout-heavy PDFs and optionally Tesseract
OCR for scanned documents would be the next step.

---

### 2. Chunking Strategy — Page-Level

One chunk per PDF page, no sub-page splitting.

Investor presentations are slide-structured. Each slide carries one coherent idea —
splitting mid-slide destroys context (a table header on one chunk, data rows on another).
Page-level chunks also give exact, unambiguous page citations. Sub-page chunking
requires tracking character offsets, which is fragile. Typical investor slides are
100–400 tokens, well within the context window of both the embedding model and the LLM.

The tradeoff: dense text pages (e.g., a 1000-word risk factors page) may be too
coarse for fine-grained retrieval. A secondary sentence-window pass would help there.

---

### 3. Embedding Model — all-MiniLM-L6-v2

Runs fully locally with no API key or cost. Produces 384-dimensional vectors and
encodes a 40-page document in under a second. Performance on short factual text is
strong enough for this use case.

The tradeoff: a larger model like `all-mpnet-base-v2` (768d) would give higher
retrieval accuracy at 2–3× inference cost. For a 40-page document the difference
is marginal; at 1,000 companies it would matter more.

---

### 4. Vector Store — Qdrant (local file mode)

Purpose-built for vector search with rich filtering support. Local file mode
(`QdrantClient(path=...)`) needs no Docker or server, data persists across restarts,
and UUID point IDs give stable reproducible chunk references. Switching to a
dedicated Qdrant server later is a single config change.

The tradeoff: local file mode uses a file lock, so concurrent writes are not safe.
A multi-user production deployment would need a separate Qdrant server process.

---

### 5. Prompting Strategy

The system prompt gives the LLM three hard rules: answer only from the provided
context, respond with a fixed refusal phrase ("The presentation does not clearly
address this.") when evidence is insufficient, and keep the answer under 200 words.
The fixed refusal phrase is important — it makes the answer detectable downstream
by the evaluation metrics without pattern-matching on free-form text.

Context is passed as labelled page blocks:
```
[Page N — Section Title]
<page text>
---
[Page M — Section Title]
<page text>
```

No few-shot examples are used. Zero-shot works reliably on llama2 for straightforward
factual retrieval tasks.

---

### 6. Citation Strategy

Citations come directly from the retrieved chunks, not from LLM output. The LLM is
not trusted to generate accurate page numbers because it frequently hallucinates them.
Instead: retrieve top_k chunks from Qdrant (each carries `page_number` and `chunk_id`),
deduplicate by page number, and return each cited page with a 150-character excerpt.
Citations are always accurate and verifiable regardless of what the LLM says.

---

### 7. Known Limitations

| Limitation | Impact |
|---|---|
| Scanned PDF pages produce empty chunks | Zero recall on image-only slides |
| Table text is flattened | Numbers extracted as prose, may confuse LLM |
| llama2 is a 7B model | Weaker reasoning than GPT-4; may miss nuanced financial logic |
| Page-level chunking is coarse | Dense pages reduce retrieval precision |
| No re-ranking | Top-k cosine similarity may miss semantically distant but relevant chunks |
| Single collection | All ingested PDFs share one index; chunks from different companies mix |
| Similarity threshold (0.30) is heuristic | May mis-classify borderline evidence as weak |

---

### 8. Scaling to 1,000 Companies

The current design handles one company in a local vector store. For 1,000:

- Add a `company` metadata filter to every Qdrant query so retrieval is scoped
  to one company's chunks. Qdrant supports this natively without separate collections.
- Move from `QdrantClient(path=...)` to `QdrantClient(host=..., port=...)` pointing
  at a Qdrant Cloud instance or self-hosted Docker container.
- Replace the API-triggered ingest with a batch pipeline (Celery + Redis) that
  processes PDFs asynchronously.
- Upgrade the embedding model to `text-embedding-3-small` (OpenAI) or `e5-large-v2`
  for better cross-domain retrieval accuracy.
- Replace llama2 with GPT-4o-mini or a fine-tuned financial LLM.
- Extract company name, fiscal year, and currency from page 1 and attach to all
  chunks, enabling multi-company comparative queries.
- Add structured JSON logging and trace each query (question → chunk IDs → answer)
  for quality monitoring.

---

## Project Structure

```
presentation_rag/
├── app/
│   ├── config.py         # Settings from .env (pydantic-settings)
│   ├── models.py         # Pydantic request/response schemas
│   ├── embedder.py       # Sentence-transformer singleton
│   ├── vector_store.py   # Qdrant client singleton + collection management
│   ├── ingest.py         # PDF parsing → chunks → embed → upsert
│   ├── retrieval.py      # Vector search
│   ├── generation.py     # Ollama prompt + answer + citations
│   ├── auth.py           # JWT auth + role-based access (admin/user)
│   ├── admin.py          # Admin-only API endpoints (/admin/*)
│   └── main.py           # FastAPI app (POST /ingest, POST /query, GET /health)
├── frontend/             # React/Vite dual-role UI
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Login.jsx     # Shared login page (redirects by role)
│   │   │   ├── Chat.jsx      # User chat interface with citations
│   │   │   └── Admin.jsx     # Admin dashboard (metrics, eval, PDF upload)
│   │   ├── AuthContext.jsx   # JWT token/role state
│   │   ├── PrivateRoute.jsx  # Role-guarded routes
│   │   ├── api.js            # Axios instance with auth interceptor
│   │   └── App.jsx           # Router + auth provider
│   ├── package.json
│   └── vite.config.js
├── tests/
│   └── test_api.py       # pytest tests
├── evaluation/
│   ├── eval_report.py    # 6-question evaluation runner (requires live API)
│   ├── auto_improve.py   # 4-metric eval, 2-round auto-improvement, winner selection
│   └── eval_metrics.json # Last evaluation output (winner config saved here)
├── streamlit_app.py      # Streamlit UI (alternative to React)
├── .env.example
├── requirements.txt
└── README.md
```
