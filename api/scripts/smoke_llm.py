#!/usr/bin/env python3
"""Smoke test: يتأكد أن karnak-6b يردّ بعربي عبر LLM_BASE_URL (OpenAI-compatible)."""
import os
import re
import sys
import time

import httpx

BASE = os.getenv("LLM_BASE_URL", "http://host.docker.internal:11434/v1")
MODEL = os.getenv("LLM_MODEL", "karnak-6b")
KEY = os.getenv("LLM_API_KEY", "ollama")
PROMPT = "اكتب جملة واحدة عن القاهرة."
ARABIC = re.compile(r"[\u0600-\u06FF]")


def main() -> int:
    started = time.time()
    try:
        with httpx.Client(timeout=180.0) as client:
            resp = client.post(
                f"{BASE}/chat/completions",
                headers={"Authorization": f"Bearer {KEY}"},
                json={
                    "model": MODEL,
                    "messages": [{"role": "user", "content": PROMPT}],
                    "max_tokens": 64,
                    "temperature": 0.3,
                },
            )
        resp.raise_for_status()
        data = resp.json()
        text = (data["choices"][0]["message"]["content"] or "").strip()
    except Exception as exc:  # noqa: BLE001 - تقرير واضح أهم من نوع الاستثناء
        print(f"FAIL: تعذّر الوصول إلى {BASE} ({exc})", file=sys.stderr)
        return 1

    elapsed = time.time() - started
    print(text)

    if not text:
        print("FAIL: الرد فارغ", file=sys.stderr)
        return 1
    if not ARABIC.search(text):
        print("FAIL: الرد لا يحتوي نصاً عربياً", file=sys.stderr)
        return 1

    tokens = (data.get("usage") or {}).get("completion_tokens") or 0
    rate = f"، ~{tokens / elapsed:.1f} tok/s" if tokens else ""
    print(f"\nOK [{MODEL}] {elapsed:.1f}s{rate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
