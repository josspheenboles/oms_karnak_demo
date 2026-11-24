import hashlib
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import make_conninfo

from app.config import settings
from app.db import get_conn
from app.main import app


def pdf(n: int = 0) -> bytes:
    return b"%PDF-1.4\n" + str(n).encode() * 50


DOCX = b"PK\x03\x04" + b"x" * 100
ARABIC_TXT = "مرحباً بكم في المعهد".encode("utf-8")


@pytest.fixture(scope="session")
def test_db_url():
    admin = make_conninfo(settings.database_url, dbname="postgres")
    with psycopg.connect(admin, autocommit=True) as c:
        if not c.execute("SELECT 1 FROM pg_database WHERE datname = 'oms_test'").fetchone():
            c.execute("CREATE DATABASE oms_test")
    return make_conninfo(settings.database_url, dbname="oms_test")


@pytest.fixture
def client(test_db_url, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_url", test_db_url)
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    with TestClient(app) as c:  # يشغّل lifespan => init_db
        with get_conn() as conn:
            conn.execute("TRUNCATE documents")
        yield c


def up(client, name, data, **form):
    return client.post("/api/v1/documents", files={"file": (name, data)}, data=form)


def test_upload_pdf_ok(client):
    r = up(client, "policy.pdf", pdf(1), space_id="hr", classification="Confidential")
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "queued"
    assert body["sha256"] == hashlib.sha256(pdf(1)).hexdigest()
    assert body["space_id"] == "hr" and body["classification"] == "Confidential"
    assert body["title"] == "policy"
    assert "stored_path" not in body
    assert (Path(settings.upload_dir) / f"{body['id']}.pdf").exists()


def test_upload_docx_and_arabic_txt(client):
    assert up(client, "دليل.docx", DOCX).status_code == 201
    r = up(client, "ملاحظات.txt", ARABIC_TXT)
    assert r.status_code == 201 and r.json()["filename"] == "ملاحظات.txt"


def test_unsupported_type(client):
    r = up(client, "virus.exe", b"MZ....")
    assert r.status_code == 415 and r.json()["detail"]["code"] == "unsupported_type"


def test_content_must_match_extension(client):
    r = up(client, "fake.pdf", b"this is plain text")
    assert r.status_code == 415 and r.json()["detail"]["code"] == "invalid_content"


def test_empty_file(client):
    r = up(client, "empty.txt", b"")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "empty_file"


def test_too_large_leaves_no_files(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 1024)
    r = up(client, "big.pdf", pdf(2) + b"y" * 5000)
    assert r.status_code == 413 and r.json()["detail"]["code"] == "file_too_large"
    assert list(Path(settings.upload_dir).iterdir()) == []


def test_duplicate_needs_confirmation(client):
    first = up(client, "a.pdf", pdf(3)).json()
    r = up(client, "b.pdf", pdf(3))
    assert r.status_code == 409
    assert r.json()["detail"]["duplicate_of"] == first["id"]
    assert up(client, "b.pdf", pdf(3), allow_duplicate="true").status_code == 201
    assert up(client, "c.pdf", pdf(3), space_id="other").status_code == 201  # space مختلف


def test_filename_is_sanitized(client):
    r = up(client, "../../evil.txt", b"hello")
    assert r.status_code == 201 and r.json()["filename"] == "evil.txt"
    files = list(Path(settings.upload_dir).iterdir())
    assert len(files) == 1 and files[0].name.endswith(".txt") and files[0].name != "evil.txt"


def test_invalid_form_values(client):
    assert up(client, "a.pdf", pdf(4), classification="Secret").status_code == 422
    assert up(client, "a.pdf", pdf(4), space_id="BAD SPACE!").status_code == 422


def test_get_and_list(client):
    d = up(client, "a.pdf", pdf(5), space_id="hr").json()
    up(client, "b.pdf", pdf(6), space_id="it")
    assert client.get(f"/api/v1/documents/{d['id']}").json()["id"] == d["id"]
    assert len(client.get("/api/v1/documents").json()) == 2
    assert len(client.get("/api/v1/documents?space_id=hr").json()) == 1
    assert client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.get("/api/v1/documents/not-a-uuid").status_code == 422
