#!/usr/bin/env python3
# تقييم سريع لـ karnak-6b على 10 أسئلة: 5 عادية، 3 RAG، 2 خارج الفقرة.
import json, time, urllib.request

URL = "http://127.0.0.1:11434/api/chat"
MODEL = "karnak-6b"

PASSAGE = """شركة نيل تك تأسست في عام 2019 في مدينة المنصورة. يعمل بها 45 موظفاً، ومقرها الرئيسي في برج النيل بالطابق السابع. أطلقت منصتها الأولى «حسابك» في مارس 2021، وحققت إيرادات قدرها 12 مليون جنيه في عام 2023. مديرها التنفيذي هو المهندس هالة سمير، وتخطط لافتتاح فرع في أسوان في عام 2027."""

RAG = "أجب اعتماداً على الفقرة التالية فقط، وإذا لم تكن المعلومة موجودة فيها قل «غير مذكور في الفقرة».\n\nالفقرة:\n" + PASSAGE + "\n\nالسؤال: "

TESTS = [
    ("عادي/فصحى 1", "ما هي عاصمة أستراليا؟ أجب في جملة واحدة."),
    ("عادي/فصحى 2", "ما الفرق بين HTTP و HTTPS؟ اشرح في جملتين."),
    ("عادي/فصحى 3", "إذا كان سعر سلعة 250 جنيهاً وعليها خصم 20%، فما السعر النهائي؟"),
    ("عادي/مصري 1", "إزاي أعمل شاي بالنعناع بطريقة صح؟ خلّيها ٣ خطوات بس."),
    ("عادي/مصري 2", "أنا عندي ٣ تفاحات وخدت منهم ٢، فاضل كام؟ رد بالمصري."),
    ("RAG 1", RAG + "متى تأسست شركة نيل تك وفي أي مدينة؟"),
    ("RAG 2", RAG + "كم عدد موظفي الشركة ومن هو مديرها التنفيذي؟"),
    ("RAG 3", RAG + "في أي سنة تخطط لافتتاح فرع أسوان، وما إيرادات عام 2023؟"),
    ("خارج الفقرة", RAG + "ما هو رقم هاتف الشركة؟"),
    ("فخ/خارج الفقرة", RAG + "كم عدد موظفي فرع أسوان؟"),
]


def ask(prompt):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"num_predict": 220, "seed": 42},
    }).encode()
    req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
    t0 = time.time()
    d = json.load(urllib.request.urlopen(req, timeout=600))
    wall = time.time() - t0
    return d, wall


results = []
for i, (name, prompt) in enumerate(TESTS, 1):
    d, wall = ask(prompt)
    msg = d["message"]["content"].strip()
    ec = d.get("eval_count") or 0
    ed = d.get("eval_duration") or 1
    pc = d.get("prompt_eval_count") or 0
    pd = d.get("prompt_eval_duration") or 1
    r = {
        "n": i, "name": name, "answer": msg,
        "gen_tps": round(ec / (ed / 1e9), 1) if ec else 0,
        "prompt_tps": round(pc / (pd / 1e9), 1) if pc else 0,
        "prompt_tokens": pc, "gen_tokens": ec, "wall_s": round(wall, 1),
    }
    results.append(r)
    print(f"\n[{i}] {name}  ({r['gen_tokens']} tok @ {r['gen_tps']} tok/s، prompt {pc} tok @ {r['prompt_tps']} tok/s، {r['wall_s']}s)")
    print(msg)

json.dump(results, open("/home/jboles/Desktop/oms/karnak-eval.json", "w"), ensure_ascii=False, indent=1)

gens = [r["gen_tps"] for r in results if r["gen_tps"]]
print("\n== متوسط السرعة ==")
print(f"توليد: {sum(gens)/len(gens):.1f} tok/s  (أدنى {min(gens)} / أعلى {max(gens)})")
print(f"زمن كلي: {sum(r['wall_s'] for r in results):.1f}s")
