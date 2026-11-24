from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .config import settings
from .db import get_conn, init_db
from .routers import documents


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    init_db()
    yield


app = FastAPI(title="OMS RAG API", version="0.1.0", lifespan=lifespan)
app.include_router(documents.router)


def _norm(name: str) -> str:
    """Ollama يخزّن karnak-6b باسم karnak-6b:latest."""
    return name[: -len(":latest")] if name.endswith(":latest") else name


def _model_present(name: str, available: set[str]) -> bool:
    return _norm(name) in {_norm(n) for n in available}


@app.get("/health")
def health():
    body: dict = {"status": "ok", "db": "up", "llm": settings.llm_model, "embed": settings.embed_model}
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1")
    except Exception:
        body["status"] = "degraded"
        body["db"] = "down"
        return JSONResponse(status_code=503, content=body)

    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{settings.ollama_url}/api/tags")
            resp.raise_for_status()
        available = {m.get("name", "") for m in resp.json().get("models", [])}
        body["ollama"] = "up"
        body["models_present"] = _model_present(settings.llm_model, available) and _model_present(
            settings.embed_model, available
        )
    except Exception:
        body["ollama"] = "down"
        body["models_present"] = False

    return body
