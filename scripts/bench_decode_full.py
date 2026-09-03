#!/usr/bin/env python3
"""C1 decode bench (Aug-28 protocol) + C4 aggregate + spec counters + thinking-toggle prefix check.

Decode tok/s = (completion_tokens - 1) / (last-delta-time - first-delta-time),
counting content + reasoning + reasoning_content delta keys (this vLLM build
streams reasoning separately). Usage-counted, temp 0, streamed.
"""
from __future__ import annotations
import json, statistics, sys, time, uuid, threading, urllib.request

BASE = "http://127.0.0.1:18888"
MODEL = "GLM-5.3-Flash-EXL3"

PROMPTS = {
    "code": ("Write a complete, idiomatic Python implementation of a binary search "
             "tree with insert, delete, search, traversal, height, docstrings, and "
             "tests. Code only."),
    "structured": ("Count from 1 to 200. Output only the numbers, separated by "
                   "spaces. No other text."),
    "math": ("A water tank is filled by two pipes. Pipe A alone fills it in 6 "
             "hours, pipe B alone in 4 hours. Pipe C can drain the full tank in "
             "12 hours. All three are opened at once. How long until the tank is "
             "full? Show every step of your work, then state the answer."),
    "prose": ("Write a detailed step-by-step explanation of how a hash map works, "
              "including collision handling, resizing, and time complexity. "
              "Be thorough."),
}

def post(body, timeout=600):
    req = urllib.request.Request(BASE + "/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)

def stream_once(prompt, thinking, max_tokens=400):
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt + " nonce=" + uuid.uuid4().hex}],
            "max_tokens": max_tokens, "temperature": 0, "stream": True,
            "stream_options": {"include_usage": True},
            "chat_template_kwargs": {"enable_thinking": thinking}}
    t_first = t_last = None; usage = None
    with post(body) as r:
        for line in r:
            if not line.startswith(b"data:"): continue
            payload = line[5:].strip()
            if payload == b"[DONE]": break
            try: chunk = json.loads(payload)
            except json.JSONDecodeError: continue
            if chunk.get("usage"): usage = chunk["usage"]
            ch = (chunk.get("choices") or [{}])[0]
            d = ch.get("delta") or {}
            if d.get("content") or d.get("reasoning") or d.get("reasoning_content"):
                now = time.monotonic()
                if t_first is None: t_first = now
                t_last = now
    ct = int((usage or {}).get("completion_tokens") or 0)
    if not t_first or ct < 2: return None
    dur = t_last - t_first
    return {"completion_tokens": ct, "decode_s": round(dur, 3),
            "tok_s": round((ct - 1) / dur, 1), "ttft_s": None}

def spec_counters():
    raw = urllib.request.urlopen(BASE + "/metrics", timeout=10).read().decode()
    out = {}
    for line in raw.splitlines():
        for k in ("vllm:spec_decode_num_drafts_total", "vllm:spec_decode_num_draft_tokens_total",
                  "vllm:spec_decode_num_accepted_tokens_total"):
            if line.startswith(k + "{") or line == k:
                out[k.split(":")[1]] = float(line.rsplit(" ", 1)[-1])
    return out

def prefix_counters():
    raw = urllib.request.urlopen(BASE + "/metrics", timeout=10).read().decode()
    hits = queries = None
    for line in raw.splitlines():
        if line.startswith("vllm:prefix_cache_hits_total"): hits = float(line.rsplit(" ", 1)[-1])
        if line.startswith("vllm:prefix_cache_queries_total"): queries = float(line.rsplit(" ", 1)[-1])
    return hits, queries

def main():
    results = {"model": MODEL, "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "c1": {}, "c4": {}, "thinking_toggle_prefix": {}}

    print("warmup (3 short requests)...", flush=True)
    for i in range(3):
        stream_once(PROMPTS["structured"][:80], False, max_tokens=32)

    for cat, prompt in PROMPTS.items():
        for thinking in (True, False):
            runs = [stream_once(prompt, thinking) for _ in range(3)]
            ok = [r for r in runs if r]
            med = round(statistics.median([r["tok_s"] for r in ok]), 1) if ok else None
            results["c1"][f"{cat}_{'thinkon' if thinking else 'thinkoff'}"] = {
                "median_tok_s": med,
                "runs": runs}
            print(f"C1 {cat} think={'on ' if thinking else 'off'}: {med} tok/s "
                  f"(runs: {[r['tok_s'] for r in ok]})", flush=True)

    # ---- C4: 4 concurrent identical-shape code requests, thinking off ----
    print("C4 aggregate (4 concurrent, think off)...", flush=True)
    outs = [None] * 4
    def worker(i):
        outs[i] = stream_once(PROMPTS["code"], False)
    t0 = time.monotonic()
    ths = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    [t.start() for t in ths]; [t.join() for t in ths]
    total_tok = sum(r["completion_tokens"] for r in outs if r)
    wall = time.monotonic() - t0
    results["c4"] = {"aggregate_tok_s": round(total_tok / wall, 1), "wall_s": round(wall, 1),
                     "total_tokens": total_tok, "per_stream": [r["tok_s"] for r in outs if r]}
    print(f"C4: {results['c4']['aggregate_tok_s']} tok/s aggregate over {wall:.0f}s", flush=True)

    # ---- thinking-toggle prefix-cache check (template fix proof) ----
    print("thinking-toggle prefix-cache check...", flush=True)
    sysm = {"role": "system", "content": "You are a helpful assistant. " + ("filler " * 1200)}
    base_hist = [sysm, {"role": "user", "content": "What is 2+2?"}]
    def chat(hist, thinking, mt=8):
        body = {"model": MODEL, "messages": hist, "max_tokens": mt, "temperature": 0,
                "chat_template_kwargs": {"enable_thinking": thinking}}
        with post(body) as r: return json.loads(r.read())
    h0, q0 = prefix_counters()
    r1 = chat(base_hist, True)                     # cold, thinking on
    h1, q1 = prefix_counters()
    r2 = chat(base_hist + [{"role": "assistant", "content": (r1.get("choices")[0]["message"].get("content") or "")},
                           {"role": "user", "content": "Now what is 3+3?"}], False)  # toggle off
    h2, q2 = prefix_counters()
    results["thinking_toggle_prefix"] = {
        "cold_hits": h1 - h0, "cold_queries": q1 - q0,
        "toggle_hits": h2 - h1, "toggle_queries": q2 - q1,
        "toggle_hit_ratio": round((h2 - h1) / max(q2 - q1, 1), 3)}
    print(f"toggle hit ratio: {results['thinking_toggle_prefix']['toggle_hit_ratio']} "
          f"(hits {h2-h1} / queries {q2-q1})", flush=True)

    spec = spec_counters()
    results["spec_counters_end"] = spec
    with open("/home/jun/glm-bench-results/bench_decode_2026-09-02.json", "w") as f:
        json.dump(results, f, indent=1)
    print("WROTE /home/jun/glm-bench-results/bench_decode_2026-09-02.json", flush=True)

if __name__ == "__main__":
    main()
