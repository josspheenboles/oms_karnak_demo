import pytest
from fastapi.testclient import TestClient

from app.db import get_conn
from app.main import app


@pytest.fixture(scope="session")
def client():
    # with => يُشغّل lifespan (init_db + إنشاء مجلد الرفع)
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_documents(client):
    with get_conn() as conn:
        conn.execute("TRUNCATE documents")
    yield
