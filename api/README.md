# OMS RAG API

FastAPI + Postgres. Ollama يعمل على الهوست (خارج compose) ويخدم:

- توليد: `karnak-6b`
- embeddings: `qwen3-embedding:0.6b`

## متطلبات لمرة واحدة على لينكس

```bash
# 1) صلاحية docker لغير root (ثم أعد تسجيل الدخول)
sudo usermod -aG docker "$USER"

# 2) اجعل Ollama يسمع على واجهة يصلها الـcontainer
#    (حالياً 127.0.0.1 فقط، وhost.docker.internal لا يصل إليه)
sudo snap set ollama host=0.0.0.0:11434
sudo snap restart ollama
ss -ltn | grep 11434   # المتوقع 0.0.0.0:11434
```

`extra_hosts: host.docker.internal:host-gateway` موجود في `docker-compose.yml` وهو شرط على لينكس.

## التشغيل

```bash
cp .env.example .env        # عدّل كلمات المرور
docker compose up -d --build
curl -s localhost:8000/health

docker compose exec api python scripts/smoke_llm.py   # رد عربي من karnak-6b
docker compose exec api pytest -q                     # اختبارات T2
```

## T2: المستندات

`POST /api/v1/documents` (multipart، ملف واحد):

| الحقل | افتراضي | ملاحظة |
|---|---|---|
| `file` | — | `.pdf .docx .txt .md` فقط |
| `title` | اسم الملف بلا امتداد | |
| `space_id` | `general` | نطاق كشف التكرار |
| `classification` | `Internal` | `Public/Internal/Confidential` |
| `allow_duplicate` | `false` | تجاوز 409 |

الاستجابة `201` بالصف كما في `documents` (الحالة `queued`).

```bash
curl -s -F file=@notes.txt localhost:8000/api/v1/documents
curl -s localhost:8000/api/v1/documents/<id>
```

أكواد الخطأ (الشكل: `{"detail": {"code", "message", ...}}`):

| HTTP | code | السبب |
|---|---|---|
| 413 | `file_too_large` | > `MAX_UPLOAD_BYTES` (50MB) |
| 415 | `unsupported_type` | امتداد غير مسموح |
| 415 | `content_mismatch` | magic bytes لا تطابق الامتداد |
| 422 | `empty_file` | ملف فارغ |
| 422 | `invalid_classification` | قيمة غير مسموحة |
| 409 | `duplicate_document` | نفس SHA-256 في نفس `space_id` (+ `duplicate_of`) |
| 404 | `not_found` | معرّف صحيح غير موجود |
| 422 | `invalid_id` | ليس UUID |

## التخزين

- الملف: `{uuid}{ext}` داخل `UPLOAD_DIR` (volume `uploads`)، والاسم الأصلي في الـDB فقط.
- SHA-256 يُحسب أثناء الكتابة المتدفّقة (لا تحميل كامل في الذاكرة).
- الجدول يُنشأ عند بدء التطبيق (`CREATE TABLE IF NOT EXISTS`). Alembic لاحقاً.

## خارج النطاق (T3–T5)

لا parsing ولا chunking ولا فهرسة. الحالة `queued` هي نقطة التسليم.
