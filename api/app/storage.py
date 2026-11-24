import codecs
import hashlib
import uuid
from pathlib import Path

from fastapi import UploadFile

from .config import settings
from .errors import api_error

ALLOWED_EXT = {".pdf", ".docx", ".txt", ".md"}
CHUNK = 1024 * 1024
HEAD_SIZE = 4096


def get_ext(filename: str) -> str:
    return Path(filename).suffix.lower()


def _content_matches(ext: str, head: bytes) -> bool:
    if ext == ".pdf":
        return b"%PDF-" in head[:1024]
    if ext == ".docx":
        return head.startswith(b"PK\x03\x04")  # DOCX = ملف zip
    # txt / md: نص UTF-8 بدون بايتات صفرية
    if b"\x00" in head:
        return False
    try:
        codecs.getincrementaldecoder("utf-8")().decode(head, final=False)
        return True
    except UnicodeDecodeError:
        return False


def save_upload(file: UploadFile, ext: str) -> tuple[Path, int, str]:
    """يكتب الملف على قرص مؤقت على دفعات، ويحسب الحجم والـ hash، ويتحقق من المحتوى.
    يرجع (المسار المؤقت, الحجم, sha256). عند أي رفض يمسح الملف المؤقت."""
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    tmp = upload_dir / f".tmp-{uuid.uuid4().hex}"
    digest = hashlib.sha256()
    size = 0
    head = b""
    try:
        with open(tmp, "wb") as out:
            while chunk := file.file.read(CHUNK):
                if not head:
                    head = chunk[:HEAD_SIZE]
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    mb = settings.max_upload_bytes // (1024 * 1024)
                    raise api_error(413, "file_too_large", f"حجم الملف أكبر من {mb}MB")
                digest.update(chunk)
                out.write(chunk)
        if size == 0:
            raise api_error(400, "empty_file", "الملف فارغ")
        if not _content_matches(ext, head):
            raise api_error(
                415, "invalid_content",
                "محتوى الملف لا يطابق امتداده (ملفات النص لازم تكون بترميز UTF-8)",
            )
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return tmp, size, digest.hexdigest()
