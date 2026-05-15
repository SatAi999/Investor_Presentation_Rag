from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.auth import require_admin
from app.config import settings
from app.vector_store import get_client

router = APIRouter(prefix="/admin", tags=["Admin"])

EVAL_METRICS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "evaluation", "eval_metrics.json"
)


@router.get("/metrics")
def get_metrics(_: dict = Depends(require_admin)):
    """Return the latest eval_metrics.json produced by auto_improve.py."""
    if not os.path.exists(EVAL_METRICS_PATH):
        return {"error": "No evaluation results found. Run auto_improve.py first."}
    with open(EVAL_METRICS_PATH, encoding="utf-8") as f:
        return json.load(f)


@router.get("/config")
def get_winner_config(_: dict = Depends(require_admin)):
    """Return the winning configuration determined by the evaluation pipeline."""
    if not os.path.exists(EVAL_METRICS_PATH):
        return {"top_k": settings.top_k, "threshold": settings.similarity_threshold, "prompt": "standard"}
    with open(EVAL_METRICS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("winner", {
        "round": "baseline",
        "settings": {"top_k": settings.top_k, "threshold": settings.similarity_threshold, "prompt": "standard"},
    })


@router.get("/collection-stats")
def collection_stats(_: dict = Depends(require_admin)):
    """Return Qdrant collection info."""
    try:
        client = get_client()
        info = client.get_collection(settings.collection_name)
        return {
            "collection": settings.collection_name,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": str(info.status),
        }
    except Exception as exc:
        return {"error": str(exc)}


async def _stream_eval() -> AsyncGenerator[str, None]:
    """Run auto_improve.py as subprocess and stream its stdout line by line."""
    project_root = os.path.join(os.path.dirname(__file__), "..")
    python_exe = sys.executable
    env = {**os.environ, "PYTHONPATH": project_root}

    process = await __import__("asyncio").create_subprocess_exec(
        python_exe,
        os.path.join(project_root, "evaluation", "auto_improve.py"),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        cwd=project_root,
    )

    async for line in process.stdout:
        text = line.decode("utf-8", errors="replace")
        yield f"data: {json.dumps({'line': text.rstrip()})}\n\n"

    await process.wait()
    yield f"data: {json.dumps({'done': True, 'exit_code': process.returncode})}\n\n"


@router.post("/run-eval")
async def run_eval(_: dict = Depends(require_admin)):
    """Stream evaluation pipeline output via Server-Sent Events."""
    return StreamingResponse(
        _stream_eval(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
