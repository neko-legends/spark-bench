#!/usr/bin/env python3
"""prewarm.py — exercise the DSV4.1 world right after boot so no Triton/DSpark kernel
JIT-compiles during real traffic (2026-09-13 wedge: _rejection_kernel, _resample_kernel,
_prepare_dflash_inputs_kernel compiled mid-inference on one rank; the TP4 collective
stalled behind it). Also a boot-quality gate: prints per-request tok/s so a slow-mode
boot is visible at boot time. Best-effort: never fails the boot.
Usage: prewarm.py [base_v1_url] [model]
"""
import json, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/v1").rstrip("/")
MODEL = sys.argv[2] if len(sys.argv) > 2 else "deepseek-v4.1-flash"
U = BASE + "/chat/completions"
T0 = time.time()


def post(body, timeout=600):
    req = urllib.request.Request(U, json.dumps(body).encode(), {"Content-Type": "application/json"})
    t = time.time()
    r = json.load(urllib.request.urlopen(req, timeout=timeout))
    return r, time.time() - t


def chat(prompt, max_tokens, thinking=False, **extra):
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens,
            "temperature": 0, "chat_template_kwargs": {"thinking": thinking}}
    body.update(extra)
    return post(body)


def report(label, r, dt):
    ct = (r.get("usage") or {}).get("completion_tokens") or 0
    print(f"[prewarm] {label:<22} {ct:>4} tok  {dt:6.1f}s  {ct / dt if dt else 0:6.1f} tok/s", flush=True)


steps = [
    ("decode-count", lambda: chat("Count from 1 to 100, separated by spaces. Output only the numbers.", 400)),
    ("decode-code", lambda: chat("Write a Python function merge_intervals(intervals) that merges overlapping intervals. Code only.", 300)),
    ("thinking-on", lambda: chat("What is 27*31? Think step by step, then answer.", 400, thinking=True)),
    ("json-format", lambda: chat('Return only a JSON object with keys name (string), count (integer), tags (array of 3 strings).', 120)),
]
for label, fn in steps:
    try:
        r, dt = fn(); report(label, r, dt)
    except Exception as exc:  # noqa: BLE001
        print(f"[prewarm] {label:<22} FAILED: {exc}", flush=True)

# tool call + tool result (DSML path)
try:
    tools = [{"type": "function", "function": {"name": "get_secret", "description": "Return the secret for a key.",
              "parameters": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}}}]
    msgs = [{"role": "user", "content": "Use the get_secret tool to fetch the value for key alpha."}]
    r1, dt1 = post({"model": MODEL, "messages": msgs, "tools": tools, "tool_choice": "auto", "max_tokens": 200, "temperature": 0})
    m1 = r1["choices"][0]["message"]; tcs = m1.get("tool_calls") or []
    if tcs:
        msgs += [{"role": "assistant", "content": m1.get("content") or "", "tool_calls": tcs},
                 {"role": "tool", "tool_call_id": tcs[0].get("id", "call_0"), "content": "{\"value\": 42}"}]
        r2, dt2 = post({"model": MODEL, "messages": msgs, "tools": tools, "max_tokens": 200, "temperature": 0})
        report("tool-roundtrip", r2, dt1 + dt2)
    else:
        print("[prewarm] tool-roundtrip        no tool call emitted", flush=True)
except Exception as exc:  # noqa: BLE001
    print(f"[prewarm] tool-roundtrip        FAILED: {exc}", flush=True)

# concurrent burst (batched decode + spec verify at bs>1)
try:
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(chat, f"Write a 120-word paragraph about topic number {i} in the history of computing.", 220) for i in range(4)]
        tot = 0; t = time.time()
        for f in futs:
            r, _ = f.result(); tot += (r.get("usage") or {}).get("completion_tokens") or 0
        dt = time.time() - t
    print(f"[prewarm] burst-c4               {tot:>4} tok  {dt:6.1f}s  {tot / dt if dt else 0:6.1f} tok/s agg", flush=True)
except Exception as exc:  # noqa: BLE001
    print(f"[prewarm] burst-c4               FAILED: {exc}", flush=True)

print(f"[prewarm] done in {time.time() - T0:.0f}s", flush=True)
