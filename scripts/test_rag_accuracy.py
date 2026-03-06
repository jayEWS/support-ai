#!/usr/bin/env python3
"""RAG accuracy batch tester - run on server"""
import json, sys, urllib.request

BASE = "http://localhost:8000"

queries = [
    ("how to update using item importer", "en"),
    ("how to set NEA item", "en"),
    ("PO web order explanation", "en"),
    ("cara closing v5", "id"),
    ("how to edit category", "en"),
    ("cara import promo pakai excel", "id"),
    ("how to do closing in v5", "en"),
    ("what is equip system", "en"),
]

print("=" * 70)
print(f"{'Query':<45} {'Conf':>6} {'Src':>4} {'Chk':>4}")
print("=" * 70)

confidences = []
for q, lang in queries:
    try:
        data = json.dumps({"query": q, "language": lang}).encode()
        req = urllib.request.Request(
            f"{BASE}/api/kb/query",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            d = json.loads(resp.read())
        c = d["confidence"]
        s = len(d["sources"])
        k = len(d.get("chunk_ids", []))
        confidences.append(c)
        print(f"{q:<45} {c:>6.4f} {s:>4} {k:>4}")
    except Exception as e:
        print(f"{q:<45} ERROR: {e}")

if confidences:
    print("=" * 70)
    avg = sum(confidences) / len(confidences)
    mx = max(confidences)
    mn = min(confidences)
    above90 = sum(1 for c in confidences if c >= 0.90)
    above80 = sum(1 for c in confidences if c >= 0.80)
    print(f"Avg confidence:  {avg:.4f}")
    print(f"Min confidence:  {mn:.4f}")
    print(f"Max confidence:  {mx:.4f}")
    print(f"Above 90%:       {above90}/{len(confidences)}")
    print(f"Above 80%:       {above80}/{len(confidences)}")
