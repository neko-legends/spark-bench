#!/usr/bin/env python3
"""Steady-state C4: 4 concurrent 1600-token streams; server-side gen rate over the steady window."""
import json, time, uuid, threading, urllib.request

BASE = "http://127.0.0.1:18888"; MODEL = "GLM-5.3-Flash-EXL3"
CODE = ("Write a complete, idiomatic Python implementation of a binary search tree with "
        "insert, delete, search, traversal, height, docstrings, and tests. Code only. "
        "Add exhaustive tests using pytest, covering edge cases.")

def post(body, timeout=900):
    req = urllib.request.Request(BASE + "/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)

def gen_rate():
    raw = urllib.request.urlopen(BASE + "/metrics", timeout=10).read().decode()
    g = q = None
    for line in raw.splitlines():
        if line.startswith("vllm:generation_tokens_total"): g = float(line.rsplit(" ", 1)[-1])
    return g

def stream_once(prompt, max_tokens):
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt + " nonce=" + uuid.uuid4().hex}],
            "max_tokens": max_tokens, "temperature": 0, "stream": True,
            "stream_options": {"include_usage": True},
            "chat_template_kwargs": {"enable_thinking": False}}
    t_first = t_last = None; usage = None
    with post(body) as r:
        for line in r:
            if not line.startswith(b"data:"): continue
            p = line[5:].strip()
            if p == b"[DONE]": break
            try: chunk = json.loads(p)
            except json.JSONDecodeError: continue
            if chunk.get("usage"): usage = chunk["usage"]
            d = ((chunk.get("choices") or [{}])[0].get("delta") or {})
            if d.get("content") or d.get("reasoning") or d.get("reasoning_content"):
                now = time.monotonic()
                if t_first is None: t_first = now
                t_last = now
    ct = int((usage or {}).get("completion_tokens") or 0)
    return {"ct": ct, "tok_s": round((ct-1)/(t_last-t_first), 1)} if t_first and ct > 1 else None

# warm the 4-batch decode shapes with one short round
short = [None]*4
def ws(i): short[i] = stream_once(CODE, 200)
ts = [threading.Thread(target=ws, args=(i,)) for i in range(4)]
[t.start() for t in ts]; [t.join() for t in ts]

# steady run: sample server gen rate while 4 x 1600-token streams run
outs = [None]*4
def w(i): outs[i] = stream_once(CODE, 1600)
ts = [threading.Thread(target=w, args=(i,)) for i in range(4)]
g0 = gen_rate(); t0 = time.monotonic()
[t.start() for t in ts]; [t.join() for t in ts]
g1 = gen_rate(); t1 = time.monotonic()
per = [r["tok_s"] for r in outs if r]
wall_rate = sum(r["ct"] for r in outs if r) / (t1 - t0)
print(json.dumps({
    "per_stream_tok_s": per,
    "client_wall_agg_tok_s": round(wall_rate, 1),
    "server_gen_rate_tok_s": round((g1-g0)/(t1-t0), 1),
    "tokens": sum(r["ct"] for r in outs if r),
    "window_s": round(t1-t0, 1)}, indent=1), flush=True)
