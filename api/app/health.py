import httpx

from .config import settings
from .db import get_conn


def _db_ok() -> bool:
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def _norm(name: str) -> str:
    """Ollama يخزّن karnak-6b باسم karnak-6b:latest."""
    return name[: -len(":latest")] if name.endswith(":latest") else name


async def _models() -> set[str]:
    async with httpx.AsyncClient(timeout=3.0) as client:
        resp = await client.get(f"{settings.ollama_url}/api/tags")
        resp.raise_for_status()
        return {_norm(m.get("name", "")) for m in resp.json().get("models", [])}


async def run_checks() -> dict[str, bool]:
    checks = {"db": _db_ok()}
    try:
        available = await _models()
    except Exception:
        checks.update({"ollama": False, "llm": False, "embed": False})
        return checks

    checks.update(
        {
            "ollama": True,
            "llm": _norm(settings.llm_model) in available,
            "embed": _norm(settings.embed_model) in available,
        }
    )
    return checks
