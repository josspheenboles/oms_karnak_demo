import hashlib
import io
import zipfile
from pathlib import Path
from uuid import uuid4

from app.config import settings


def _docx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
    return buf.getvalue()


def _upload(client, name: str, content: bytes, **form):
    return client.post(
        "/api/v1/documents",
        files={"file": (name, content, "application/octet-stream")},
        data=form,
    )


def test_upload_txt_is_queued(client):
    content = "عاصمة مصر هي القاهرة.\n".encode()
    resp = _upload(client, "note.txt", content)

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    assert body["ext"] == ".txt"
    assert body["size_bytes"] == len(content)
    assert body["sha256"] == hashlib.sha256(content).hexdigest()
    assert body["filename"] == "note.txt"
    assert body["title"] == "note"
    assert body["owner_id"] == "demo-user"
    assert body["space_id"] == "general"
    assert body["classification"] == "Internal"

    stored = Path(body["stored_path"])
    assert stored.exists()
    assert stored.name.endswith(".txt")
    assert len(stored.stem) == 32  # uuid4().hex
    assert stored.read_bytes() == content


def test_upload_markdown_and_docx(client):
    assert _upload(client, "readme.md", "# عنوان\n".encode()).status_code == 201
    assert _upload(client, "doc.docx", _docx_bytes()).status_code == 201


def test_get_document(client):
    created = _upload(client, "a.txt", b"hello").json()

    resp = client.get(f"/api/v1/documents/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]
    assert resp.json()["status"] == "queued"

    assert client.get(f"/api/v1/documents/{uuid4()}").status_code == 404
    assert client.get("/api/v1/documents/not-a-uuid").status_code == 422


def test_fake_pdf_rejected_by_magic_bytes(client):
    resp = _upload(client, "fake.pdf", b"this is not a pdf")
    assert resp.status_code == 415
    assert resp.json()["detail"]["code"] == "content_mismatch"

    ok = _upload(client, "real.pdf", b"%PDF-1.7\n...\n%%EOF")
    assert ok.status_code == 201


def test_binary_txt_rejected(client):
    resp = _upload(client, "bin.txt", b"\x00\x01\x02binary")
    assert resp.status_code == 415
    assert resp.json()["detail"]["code"] == "content_mismatch"


def test_unsupported_and_empty_and_oversize(client, monkeypatch):
    resp = _upload(client, "evil.exe", b"MZ")
    assert resp.status_code == 415
    assert resp.json()["detail"]["code"] == "unsupported_type"

    resp = _upload(client, "empty.txt", b"")
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "empty_file"

    monkeypatch.setattr(settings, "max_upload_bytes", 10)
    resp = _upload(client, "big.txt", b"x" * 11)
    assert resp.status_code == 413
    assert resp.json()["detail"]["code"] == "file_too_large"


def test_duplicate_returns_409_then_override(client):
    content = b"same bytes"
    first = _upload(client, "one.txt", content)
    assert first.status_code == 201

    dup = _upload(client, "two.txt", content)
    assert dup.status_code == 409
    detail = dup.json()["detail"]
    assert detail["code"] == "duplicate_document"
    assert detail["duplicate_of"] == first.json()["id"]

    forced = _upload(client, "two.txt", content, allow_duplicate="true")
    assert forced.status_code == 201
    assert forced.json()["id"] != first.json()["id"]

    other_space = _upload(client, "two.txt", content, space_id="hr")
    assert other_space.status_code == 201


def test_filename_cannot_escape_upload_dir(client):
    resp = _upload(client, "../../etc/passwd.txt", b"root:x:0:0")
    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "passwd.txt"
    assert ".." not in body["stored_path"]
    assert Path(body["stored_path"]).parent == Path(settings.upload_dir)
