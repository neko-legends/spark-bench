#!/usr/bin/env python3
"""Phase-4 arm gates: arithmetic, JSON, tool round-trip (phase-1 corruption repro, chat render),
corrcheck-style 7-check pass, and NIAH needles.

Fails closed (exit 3) if any check fails. Usage:
  gates.py --label <arm-label> [--niah-targets 32768] [--niah-depths 0.25,0.5,0.75] [--skip-niah] [--out DIR]
NIAH uses tony/bench/v41needle.py as a module (same filler calibration).
"""
import argparse, json, subprocess, sys, time, urllib.request
from datetime import datetime, timezone

BASE = "http://192.168.10.1:8000"
MODEL = "deepseek-v4.1-flash"
NEEDLE = "/home/jun/dsv41-vllm/tony/bench/v41needle.py"
results = []

def call(body, timeout=600):
    req = urllib.request.Request(BASE + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))

def check(name, ok, detail=""):
    results.append({"check": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(("PASS " if ok else "FAIL ") + name + (" — " + str(detail)[:200] if detail else ""), flush=True)

def finish(label):
    ok = all(r["ok"] for r in results)
    out = {"label": label, "ts": datetime.now(timezone.utc).isoformat(), "ok": ok, "checks": results}
    print(json.dumps(out))
    sys.exit(0 if ok else 3)

base = {"model": MODEL, "temperature": 0, "chat_template_kwargs": {"thinking": False}}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="arm")
    ap.add_argument("--niah-targets", default="32768")
    ap.add_argument("--niah-depths", default="0.25,0.5,0.75")
    ap.add_argument("--niah-timeout-depth", default="400000", help="extra big target for the 420k gate")
    ap.add_argument("--skip-niah", action="store_true")
    ap.add_argument("--out", default="/home/jun/dsv41-vllm/phase4")
    args = ap.parse_args()
    label = args.label

    # 1. arithmetic (thinking off)
    try:
        r = call({**base, "messages": [{"role": "user", "content": "Compute 19 + 23. Reply with the number only."}], "max_tokens": 16})
        msg = r["choices"][0]["message"]
        c = (msg.get("content") or "").strip()
        rt = (r["choices"][0].get("reasoning_content") or "")
        check("arithmetic_19plus23", c == "42" and r["choices"][0].get("finish_reason") == "stop" and not rt,
              f"content={c!r} finish={r['choices'][0].get('finish_reason')} reasoning={bool(rt)}")
    except Exception as e:
        check("arithmetic_19plus23", False, repr(e)); finish(label)

    # 2. JSON strict
    try:
        r = call({**base, "messages": [{"role": "user", "content": "Return ONLY the JSON object {\"answer\": 42} and nothing else."}], "max_tokens": 64})
        c = (r["choices"][0]["message"].get("content") or "").strip()
        parsed = None
        try:
            parsed = json.loads(c)
        except Exception:
            parsed = None
        check("json_schema", isinstance(parsed, dict) and parsed.get("answer") == 42, f"parsed={parsed!r}")
    except Exception as e:
        check("json_schema", False, repr(e)); finish(label)

    # 3+4. tool call explicit + round-trip continuation (phase-1 SGLang corruption repro, DSML chat render)
    tool_payload = {"type": "function", "function": {"name": "lookup_fixture",
        "description": "Retrieve a stored test value.",
        "parameters": {"type": "object", "properties": {"key": {"type": "string"}},
                       "required": ["key"], "additionalProperties": False}}}
    assistant_call = {"role": "assistant",
        "content": "I'll retrieve the value for key \"alpha\" using the lookup_fixture tool.",
        "tool_calls": [{"id": "call_1", "type": "function",
                        "function": {"name": "lookup_fixture", "arguments": "{\"key\": \"alpha\"}"}}]}
    tool_result = {"role": "tool", "tool_call_id": "call_1", "content": "{\"value\":42}"}
    try:
        r = call({**base, "messages": [{"role": "user", "content": "Use lookup_fixture to retrieve the value for key alpha. Do not guess."}],
                  "tools": [tool_payload], "tool_choice": "auto", "max_tokens": 512})
        msg = r["choices"][0]["message"]
        tcs = msg.get("tool_calls") or []
        ok = bool(tcs) and tcs[0]["function"]["name"] == "lookup_fixture"
        if ok:
            try:
                a = json.loads(tcs[0]["function"].get("args") or tcs[0]["function"].get("arguments"))
                ok = a.get("key") == "alpha"
            except Exception:
                ok = False
        check("tool_call_explicit", ok, str(tcs[:1])[:200])
    except Exception as e:
        check("tool_call_explicit", False, repr(e)); finish(label)
    try:
        r = call({**base, "messages": [
                      {"role": "system", "content": "", "tools": [tool_payload]},
                      {"role": "user", "content": "Use lookup_fixture to retrieve the value for key alpha. Do not guess."},
                      assistant_call, tool_result],
                  "tools": [tool_payload], "max_tokens": 512})
        c = (r["choices"][0]["message"].get("content") or "")
        fin = r["choices"][0].get("finish_reason")
        ok = ("42" in c) and ("</tool_result>" not in c) and (fin == "stop")
        check("tool_roundtrip_repro", ok, f"finish={fin} content={c[:120]!r}")
    except Exception as e:
        check("tool_roundtrip_repro", False, repr(e)); finish(label)

    # 5. temp0 determinism (corrcheck-style)
    try:
        import hashlib
        hs = []
        for _ in range(2):
            r = call({**base, "messages": [{"role": "user", "content": "What is the capital of Australia? Just the city."}], "max_tokens": 64})
            c = (r["choices"][0]["message"].get("content") or "")
            hs.append(hashlib.sha256(c.encode()).hexdigest()[:12])
        check("temp0_deterministic", len(set(hs)) == 1, str(hs))
    except Exception as e:
        check("temp0_deterministic", False, repr(e)); finish(label)

    # 6. NIAH needles via v41needle.py
    if not args.skip_niah:
        depths = [d for d in args.niah_depths.split(",") if d]
        niah_rows = []
        for tgt in [t for t in args.niah_targets.split(",") if t]:
            for d in depths:
                p = subprocess.run([sys.executable, NEEDLE, "--base", BASE + "/v1", "--model", MODEL,
                                    "--targets", tgt, "--depth", d],
                                   capture_output=True, text=True, timeout=3600)
                rows = None
                for line in p.stdout.splitlines():
                    if line.startswith("{") and '"pass"' in line:
                        rows = json.loads(line)
                ok = bool(rows and rows.get("pass"))
                niah_rows.append(rows)
                check(f"niah_{tgt}_d{d}", ok, str(rows)[:200] if rows else p.stdout[-200:])
        # big-context needle (420k gate): single depth 0.5, long TTFT allowed
        if args.niah_timeout_depth and int(args.niah_timeout_depth) > 0:
            tgt = args.niah_timeout_depth
            p = subprocess.run([sys.executable, NEEDLE, "--base", BASE + "/v1", "--model", MODEL,
                                "--targets", tgt, "--depth", "0.5"],
                               capture_output=True, text=True, timeout=3600)
            rows = None
            for line in p.stdout.splitlines():
                if line.startswith("{") and '"pass"' in line:
                    rows = json.loads(line)
            check(f"niah_{tgt}_d0.5", bool(rows and rows.get("pass")), str(rows)[:200] if rows else p.stdout[-200:])

    finish(label)

if __name__ == "__main__":
    main()
