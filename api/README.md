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
docker compose exec api pytest -v                     # T1 + T2
```

الاختبارات تعمل على قاعدة منفصلة `oms_test` (تُنشأ تلقائياً)، و`TRUNCATE` لا يمسّ بيانات التطوير.

## T2: المستندات

`POST /api/v1/documents` (multipart، ملف واحد):

| الحقل | افتراضي | ملاحظة |
|---|---|---|
| `file` | — | `.pdf .docx .txt .md` فقط |
| `space_id` | `general` | `^[a-z0-9_-]{1,64}$` |
| `classification` | `Internal` | `Public/Internal/Confidential` |
| `title` | اسم الملف بلا امتداد | |
| `allow_duplicate` | `false` | تجاوز 409 |

```bash
curl -F "file=@sample.pdf" -F "space_id=hr" -F "classification=Internal" \
  localhost:8000/api/v1/documents
curl localhost:8000/api/v1/documents/<id>
curl "localhost:8000/api/v1/documents?space_id=hr&limit=20"
docker compose exec postgres psql -U oms -d oms -c "select id, filename, status from documents;"
ls data/uploads
```

أكواد الخطأ (الشكل: `{"detail": {"code", "message", ...}}`):

| HTTP | code | السبب |
|---|---|---|
| 413 | `file_too_large` | > `MAX_UPLOAD_BYTES` (50MB) |
| 415 | `unsupported_type` | امتداد غير مسموح |
| 415 | `invalid_content` | المحتوى لا يطابق الامتداد |
| 400 | `empty_file` | ملف فارغ |
| 409 | `duplicate` | نفس SHA-256 في نفس `space_id` (+ `duplicate_of`) |
| 404 | `not_found` | معرّف صحيح غير موجود |
| 422 | — | `space_id`/`classification` غير صالحين، أو id ليس UUID |

## التخزين

- الملف: `{uuid}{ext}` داخل `UPLOAD_DIR`، والاسم الأصلي في الـDB فقط.
- `stored_path` لا يظهر في أي رد.
- SHA-256 يُحسب أثناء كتابة متدفّقة (1MB chunks)، والتحقق من المحتوى على أول 4KB.
- الجدول يُنشأ عند بدء التطبيق (`CREATE TABLE IF NOT EXISTS`). Alembic لاحقاً.

## خارج النطاق (T3–T5)

لا parsing ولا chunking ولا فهرسة. الحالة `queued` هي نقطة التسليم.
