import hashlib
import zipfile
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, File, Form, UploadFile

from ..config import settings
from ..db import find_by_hash, get_document, insert_document
from ..errors import api_error

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

ALLOWED_EXT = {".pdf", ".docx", ".txt", ".md"}
CLASSIFICATIONS = {"Public", "Internal", "Confidential"}
TEXT_EXT = {".txt", ".md"}
CHUNK = 1024 * 1024


def _safe_filename(name: str | None) -> str:
    """اسم الملف الأصلي بعد إزالة أي مسار (path traversal)."""
    base = (name or "").replace("\\", "/").split("/")[-1].strip()
    return base


def _looks_textual(head: bytes) -> bool:
    if b"\x00" in head:
        return False
    for enc in ("utf-8", "cp1256"):
        try:
            head.decode(enc)
            return True
        except UnicodeDecodeError:
            continue
    return False


def _check_content(path: Path, ext: str) -> None:
    """فحص magic bytes/بنية الملف — التحقق العميق متروك للـparser في T3."""
    with path.open("rb") as fh:
        head = fh.read(8192)

    if ext == ".pdf" and not head.startswith(b"%PDF-"):
        raise api_error(415, "content_mismatch", "المحتوى لا يطابق صيغة PDF")

    if ext == ".docx":
        if not head.startswith(b"PK\x03\x04"):
            raise api_error(415, "content_mismatch", "المحتوى لا يطابق صيغة DOCX")
        try:
            with zipfile.ZipFile(path) as archive:
                if "[Content_Types].xml" not in archive.namelist():
                    raise api_error(415, "content_mismatch", "المحتوى لا يطابق صيغة DOCX")
        except zipfile.BadZipFile:
            raise api_error(415, "content_mismatch", "المحتوى لا يطابق صيغة DOCX")

    if ext in TEXT_EXT and not _looks_textual(head):
        raise api_error(415, "content_mismatch", "الملف يبدو ثنائياً لا نصياً")


async def _store_tmp(file: UploadFile, ext: str) -> tuple[Path, int, str]:
    """يحفظ الملف مؤقتاً أثناء حساب SHA-256 ويفرض حد الحجم."""
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    tmp = upload_dir / f".tmp-{uuid4().hex}"
    digest = hashlib.sha256()
    size = 0
    try:
        with tmp.open("wb") as out:
            while chunk := await file.read(CHUNK):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise api_error(
                        413,
                        "file_too_large",
                        f"حجم الملف يتجاوز الحد الأقصى ({settings.max_upload_bytes} بايت)",
                    )
                digest.update(chunk)
                out.write(chunk)
        if size == 0:
            raise api_error(422, "empty_file", "الملف فارغ")
        _check_content(tmp, ext)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return tmp, size, digest.hexdigest()


@router.post("", status_code=201)
async def create_document(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    space_id: str = Form("general"),
    classification: str = Form("Internal"),
    allow_duplicate: bool = Form(False),
):
    filename = _safe_filename(file.filename)
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise api_error(
            415,
            "unsupported_type",
            f"نوع غير مدعوم. المسموح: {', '.join(sorted(ALLOWED_EXT))}",
        )
    if classification not in CLASSIFICATIONS:
        raise api_error(
            422, "invalid_classification", "classification يجب أن تكون Public/Internal/Confidential"
        )

    tmp, size, sha256 = await _store_tmp(file, ext)

    existing = find_by_hash(space_id, sha256)
    if existing and not allow_duplicate:
        tmp.unlink(missing_ok=True)
        raise api_error(
            409,
            "duplicate_document",
            "نفس الملف موجود بالفعل في هذا الفضاء. أعد المحاولة مع allow_duplicate=true.",
            duplicate_of=str(existing["id"]),
        )

    stored = Path(settings.upload_dir) / f"{uuid4().hex}{ext}"
    tmp.replace(stored)

    return insert_document(
        title=title or Path(filename).stem or "document",
        filename=filename,
        ext=ext,
        size_bytes=size,
        sha256=sha256,
        stored_path=str(stored),
        space_id=space_id,
        classification=classification,
        owner_id="demo-user",
        status="queued",
    )


@router.get("/{doc_id}")
def read_document(doc_id: str):
    try:
        UUID(doc_id)
    except ValueError:
        raise api_error(422, "invalid_id", "المعرّف ليس UUID صالحاً")

    row = get_document(doc_id)
    if row is None:
        raise api_error(404, "not_found", "لا يوجد مستند بهذا المعرّف")
    return row
