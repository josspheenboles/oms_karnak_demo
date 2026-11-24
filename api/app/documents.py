import os
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, File, Form, UploadFile

from .config import settings
from .db import get_conn
from .errors import api_error
from .storage import ALLOWED_EXT, get_ext, save_upload

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

# stored_path مش بيطلع في أي رد (ما نكشفش مسارات السيرفر)
COLS = ("id, title, filename, ext, size_bytes, sha256, space_id, classification, "
        "owner_id, status, error_reason, created_at")


def _clean_filename(name: str | None) -> str:
    return os.path.basename((name or "").replace("\\", "/")).strip()[:255]


@router.post("", status_code=201)
def upload_document(
    file: Annotated[UploadFile, File()],
    space_id: Annotated[str, Form(pattern=r"^[a-z0-9_-]{1,64}$")] = "general",
    classification: Literal["Public", "Internal", "Confidential"] = Form("Internal"),
    title: Annotated[str | None, Form()] = None,
    allow_duplicate: Annotated[bool, Form()] = False,
):
    original = _clean_filename(file.filename)
    ext = get_ext(original)
    if ext not in ALLOWED_EXT:
        raise api_error(
            415, "unsupported_type",
            f"نوع الملف غير مدعوم. المسموح: {', '.join(sorted(ALLOWED_EXT))}",
        )

    tmp, size, sha = save_upload(file, ext)
    final: Path | None = None
    try:
        with get_conn() as conn:
            dup = conn.execute(
                "SELECT id FROM documents WHERE space_id = %s AND sha256 = %s "
                "ORDER BY created_at LIMIT 1",
                (space_id, sha),
            ).fetchone()
            if dup and not allow_duplicate:
                raise api_error(
                    409, "duplicate", "نفس الملف مرفوع من قبل في هذا الـ space",
                    duplicate_of=str(dup["id"]),
                )
            doc_id = uuid4()
            final = Path(settings.upload_dir) / f"{doc_id}{ext}"
            os.replace(tmp, final)
            row = conn.execute(
                f"INSERT INTO documents (id, title, filename, ext, size_bytes, sha256, "
                f"stored_path, space_id, classification) "
                f"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING {COLS}",
                (doc_id, (title or Path(original).stem).strip()[:200] or original,
                 original, ext, size, sha, str(final), space_id, classification),
            ).fetchone()
    except BaseException:
        tmp.unlink(missing_ok=True)
        if final:
            final.unlink(missing_ok=True)
        raise
    return row


@router.get("/{doc_id}")
def get_document(doc_id: UUID):
    with get_conn() as conn:
        row = conn.execute(f"SELECT {COLS} FROM documents WHERE id = %s", (doc_id,)).fetchone()
    if not row:
        raise api_error(404, "not_found", "المستند غير موجود")
    return row


@router.get("")
def list_documents(space_id: str | None = None, limit: int = 100):
    limit = max(1, min(limit, 500))
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT {COLS} FROM documents WHERE (%s::text IS NULL OR space_id = %s) "
            f"ORDER BY created_at DESC LIMIT %s",
            (space_id, space_id, limit),
        ).fetchall()
    return rows
