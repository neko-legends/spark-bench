#!/usr/bin/env python3
"""30-generation structured-output garble gate, 6 requests in flight. Usage: v41gate.py <base_v1_url> <model>"""
import json, re, sys, urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
U = sys.argv[1].rstrip("/") + "/chat/completions"; M = sys.argv[2]
P = [("json", "Return only a JSON object with keys name (string), count (integer), tags (array of 3 strings). No prose.", 120),
     ("tool", 'Extract to JSON: "Meet Ana at 3pm Tuesday at Cafe Rio for 45 minutes." Keys: who, time, day, place, duration_min.', 120),
     ("code", "Write a Python one-liner that reverses a string s. Only the code.", 60)]
def garbled(t):
    if not t or not t.strip(): return "EMPTY"
    cjk = len(re.findall(r"[一-鿿]", t))
    if cjk > len(t) * 0.10: return f"CJK {cjk}"
    w = re.findall(r"\S+", t)
    if len(w) > 12:
        top = Counter(w).most_common(1)[0]
        if top[1] > len(w) * 0.4: return f"REPEAT {top[0]!r}x{top[1]}"
    if re.search(r"(.{12,}?)\1{3,}", t): return "LOOPFRAG"
    return None
jobs = [(temp, name, p, mt, i) for temp in (0.0, 0.7, 1.0) for name, p, mt in P for i in range(4 if temp else 2)]
def run(job):
    temp, name, p, mt, i = job
    body = json.dumps({"model": M, "messages": [{"role": "user", "content": p}], "max_tokens": mt,
                       "temperature": temp, "stream": False}).encode()
    r = json.load(urllib.request.urlopen(urllib.request.Request(U, body, {"Content-Type": "application/json"}), timeout=600))
    return job, r["choices"][0]["message"].get("content") or ""
bad = n = 0
with ThreadPoolExecutor(max_workers=6) as ex:
    for (temp, name, p, mt, i), t in ex.map(run, jobs):
        n += 1
        g = garbled(t)
        if g: bad += 1; print(f"  GARBLE t{temp} {name}#{i}: {g} | {t[:60]!r}")
print(f"{n-bad}/{n} clean ({bad} garbled)")
sys.exit(1 if bad > n * 0.1 else 0)
