from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_conn
from app.main import app


def test_health_reports_db_and_models(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    with TestClient(app) as client:  # lifespan => init_db
        resp = client.get("/health")
        body = resp.json()

    assert resp.status_code == 200
    assert body["db"] is True
    assert set(body) >= {"status", "db", "ollama", "llm", "embed"}
    assert all(isinstance(body[k], bool) for k in ("db", "ollama", "llm", "embed"))
    # لا نلزم وجود Ollama في بيئة الاختبار
    assert body["status"] in {"ok", "degraded"}
    with get_conn() as conn:
        conn.execute("SELECT 1")
