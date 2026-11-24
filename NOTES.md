# Karnak-6B-v1.0 → Ollama (Q4_K_M)

سجلّ لما تم تنفيذه على هذا الجهاز (Linux, CPU-only, 15 GB RAM).

## 1) تنزيل الأوزان

```bash
hf download Applied-Innovation-Center/Karnak-6B-v1.0 --local-dir karnak-6b
# 11.9 GB — تم التحقق من أحجام الملفات الثلاثة (safetensors)
```

## 2) المحاولة الأولى (مسار A) — فشلت

```bash
ollama create --quantize q4_K_M karnak-6b -f Modelfile
```

- `Error: unsupported --quantize "q4_K_M": supported types are int4, int8, nvfp4, mxfp4, mxfp8`
- و`--quantize int4` أعطى: `MLX runtime is not available` → التكميم المدمج في Ollama 0.40.2
  على Linux يحتاج MLX (أي Apple Silicon)، ولا يدعم q4_K_M أساساً.

## 3) المسار B — llama.cpp (نجح)

```bash
# binaries + المصدر (سكربت التحويل صار يستورد حزمة conversion/)
curl -L -o tools/llama-bin.tar.gz \
  https://github.com/ggml-org/llama.cpp/releases/download/b12674/llama-b12674-bin-ubuntu-x64.tar.gz
git clone --depth 1 --branch b12674 https://github.com/ggml-org/llama.cpp.git tools/llama-src

python3 -m venv tools/venv
tools/venv/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch
tools/venv/bin/pip install transformers sentencepiece gguf safetensors tqdm protobuf

# bf16 GGUF (~48 ثانية)
tools/venv/bin/python tools/llama-src/convert_hf_to_gguf.py karnak-6b \
  --outfile karnak-6b-bf16.gguf --outtype bf16

# Q4_K_M (~2.2 دقيقة)
tools/llama-b12674/llama-quantize karnak-6b-bf16.gguf karnak-6b-Q4_K_M.gguf Q4_K_M 8
```

## 4) استيراد إلى Ollama

`Modelfile` يستخدم `FROM ./karnak-6b-Q4_K_M.gguf`، ثم:

```bash
ollama create karnak-6b -f Modelfile
ollama run karnak-6b
```

النتيجة: `karnak-6b:latest` بحجم 3.7 GB، `qwen3`، `Q4_K_M`، `num_ctx 8192`.

## ملاحظات

- Ollama يستخدم `chat_template.jinja` المضمّن في GGUF (قالب الموديل الرسمي) بدل قالب
  Modelfile — وهذا أفضل، ونظام Karnak يُمرَّر عبر `SYSTEM`.
- الأداء على CPU (8 threads): ~11 tok/s توليد، ~49 tok/s معالجة prompt.
- `karnak-6b-bf16.gguf` (12 GB) غير مطلوب بعد الاستيراد؛ يمكن حذفه لتوفير المساحة.
