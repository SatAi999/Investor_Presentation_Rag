from __future__ import annotations

import os
import shutil
import tempfile

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends

from app.admin import router as admin_router
from app.auth import authenticate, create_access_token, get_current_user
from app.config import settings
from app.generation import generate_answer
from app.ingest import ingest_pdf
from app.models import IngestResponse, QueryRequest, QueryResponse
from app.retrieval import retrieve

app = FastAPI(
    title="Investor Presentation RAG",
    description="Question-answering over investor presentations with page-level citations.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router)


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/auth/login", tags=["Auth"])
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = authenticate(form.username, form.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token(user["username"], user["role"])
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}


@app.get("/auth/me", tags=["Auth"])
def me(user: dict = Depends(get_current_user)):
    return user


@app.get("/health", tags=["System"])
def health():
    return {
        "status": "ok",
        "ollama_model": settings.ollama_model,
        "embedding_model": settings.embedding_model,
        "collection": settings.collection_name,
    }


@app.post("/ingest", response_model=IngestResponse, tags=["Ingestion"])
async def ingest(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    doc_name = os.path.splitext(file.filename)[0]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        chunk_count = ingest_pdf(tmp_path, doc_name)
    finally:
        os.unlink(tmp_path)

    if chunk_count == 0:
        raise HTTPException(
            status_code=422,
            detail="PDF produced no extractable text. It may be a scanned image PDF.",
        )

    return IngestResponse(
        status="success",
        chunk_count=chunk_count,
        document=doc_name,
        message=f"Successfully ingested {chunk_count} page-level chunks from '{doc_name}'.",
    )


@app.post("/query", response_model=QueryResponse, tags=["Query"])
def query(request: QueryRequest):
    chunks_with_scores = retrieve(request.question, top_k=request.top_k)
    return generate_answer(request.question, chunks_with_scores, top_k=request.top_k)
