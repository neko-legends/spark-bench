#!/usr/bin/env python3
"""Mixed-prefill guard: does a big cold prefill collapse the C4 steady decode?

This is the ruler that gives decode-floor / GLM53_MIXED_PREFILL_SMALL_OK /
LONG_PREFILL_TOKEN_THRESHOLD their fair trial: a pure-C4 ruler contains no
prefill traffic, so those patches can only ever show cost on it (measurement
audit, Task 2.7).

Protocol: run a normal C4 steady window (reusing bench_c4_steady functions —
same frozen CODE prompt, end-nonce, temp 0, thinking off, 4x1600 tokens), and
inject ONE front-salted ~16k-token cold prefill mid-window. The salt is a
unique random PREFIX (unlike the C4 ruler's end-nonce), so the injected
prompt cannot hit the prefix cache — cached_tokens in the response proves the
cold regime per request (no cache flushes on the shared serve).

Reported:
- injected-request TTFT (and prompt_tokens / cached_tokens / finish_reason)
- C4 steady_agg retention = guard-pass steady_agg / baseline-pass steady_agg
- max per-stream inter-delta stall (guard pass vs baseline pass)

Usage:
  python3 bench_mixed_guard.py [--base http://127.0.0.1:18888]
                                [--inject-tokens 16000] [--inject-delay 10]
                                [--out DIR] [--self-test]

--out writes mixedguard-<UTC>-c4.json with O_EXCL (never overwrite).
Python 3.10+ stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import threading
import time
import urllib.request
import uuid
from pathlib import Path

import bench_c4_steady as c4
import run_cold_prefill_18888 as rcp

NAME = "mixedguard"
DEFAULT_INJECT_TOKENS = 16_000
DEFAULT_INJECT_DELAY_S = 10.0


def build_injected_prompt(target_tokens: int) -> tuple[str, int, int]:
    """Front-salted ~target_tokens prompt via /tokenize calibration (unique
    random prefix first, so the prefix cache cannot be warm for it)."""
    salt = f"MIXED-GUARD salt={uuid.uuid4()} pad={secrets.token_hex(24)}"
    # calibrate against the same serve the guard runs on
    n, tok_est, text = rcp.calibrate(target_tokens, salt, timeout=180.0)
    return text, n, tok_est


def run_guard_pass(inject_prompt: str, inject_delay_s: float, max_tokens: int = c4.MAX_TOKENS):
    """C4 steady pass with one mid-window cold-prefill injection.

    Like c4.run_pass but: (a) the injected request runs mid-window in the
    main thread; (b) the post-window generation-token delta must equal
    Σct + injected completion tokens, or the pass is flagged invalid.
    """
    outs = [None] * 4
    def w(i): outs[i] = c4.stream_once(c4.CODE, max_tokens)
    ts = [threading.Thread(target=w, args=(i,)) for i in range(4)]
    pre = c4.metrics_snapshot()
    t0 = time.monotonic()
    [t.start() for t in ts]
    time.sleep(inject_delay_s)
    injected = rcp.stream_chat(rcp.chat_messages(inject_prompt), timeout=600)
    inj_t = time.monotonic()
    [t.join() for t in ts]
    t1 = time.monotonic()
    post = c4.metrics_snapshot()

    res = c4.evaluate_pass(outs, pre, post, t0, t1, max_tokens)
    inj_ct = int(injected.get("completion_tokens") or 0)
    # re-evaluate the gen-delta condition including the injected request's tokens
    reasons = [r for r in res["invalid_reasons"] if not r.startswith("gen_delta=")]
    g0, g1 = pre.get("generation_tokens_total"), post.get("generation_tokens_total")
    gen_delta = round(g1 - g0, 1) if (g0 is not None and g1 is not None) else None
    sum_ct = res["tokens"]
    if gen_delta is None:
        reasons.append("generation_tokens_total_unavailable")
    elif abs(gen_delta - (sum_ct + inj_ct)) > 1.0:
        reasons.append(f"gen_delta={gen_delta}!=sum_ct+injected={sum_ct + inj_ct}")
    res["invalid_reasons"] = reasons
    res["valid"] = not reasons
    res["inject_offset_s"] = round(inj_t - t0, 1)
    res["injected"] = {k: injected.get(k) for k in
                       ("ttft_s", "prompt_tokens", "cached_tokens", "completion_tokens",
                        "finish_reason", "prefill_tok_s", "wall_s", "error")}
    return res


def max_stall_ms(res) -> float | None:
    """Max inter-delta gap across the C4 streams in a pass (ms)."""
    gaps = []
    for r in (res.get("per_stream") or []):
        if r and not r.get("error") and r.get("gaps"):
            gaps.extend(r["gaps"])
    return round(max(gaps) * 1000, 1) if gaps else None


def summarize(baseline, guard):
    b_steady = baseline.get("steady_agg_tok_s")
    g_steady = guard.get("steady_agg_tok_s")
    retention = round(g_steady / b_steady, 3) if (b_steady and g_steady) else None
    b_max = max_stall_ms(baseline)
    g_max = max_stall_ms(guard)
    stall_delta = round(g_max - b_max, 1) if (g_max is not None and b_max is not None) else None
    return {
        "schema": "mixed_guard_v1",
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "baseline_pass": baseline,
        "guard_pass": guard,
        "injected": guard.get("injected"),
        "steady_agg_retention": retention,
        "baseline_steady_agg_tok_s": b_steady,
        "guard_steady_agg_tok_s": g_steady,
        "baseline_max_stall_ms": b_max,
        "guard_max_stall_ms": g_max,
        "max_stall_delta_ms": stall_delta,
        "config": {**c4.config_block(),
                   "inject_tokens_target": None,
                   "inject_delay_s": None},
    }


def write_excl(path: Path, obj) -> None:
    data = json.dumps(obj, indent=1) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w") as f:
        f.write(data)


# --------------------------- offline self-test ---------------------------

def self_test() -> int:
    import tempfile
    fails = []
    def check(name, cond):
        print(("PASS" if cond else "FAIL") + f" {name}", flush=True)
        if not cond: fails.append(name)

    # max_stall_ms over synthetic records
    res = {"per_stream": [{"error": None, "gaps": [0.01, 0.02, 0.05]},
                           {"error": None, "gaps": [0.01, 0.03]},
                           {"error": "x", "gaps": [9.9]},
                           None]}
    check("max_stall_ms", max_stall_ms(res) == 50.0)
    check("max_stall_ms empty", max_stall_ms({"per_stream": []}) is None)

    # retention math
    s = summarize({"steady_agg_tok_s": 128.9}, {"steady_agg_tok_s": 122.5, "injected": {"ttft_s": 3.2}})
    check("retention math", s["steady_agg_retention"] == 0.95)
    check("summary carries injected", s["injected"]["ttft_s"] == 3.2)
    check("stall delta", s["max_stall_delta_ms"] is None)  # no per_stream data

    # guard validity: gen delta must include injected tokens
    pre = {"generation_tokens_total": 0.0, "per_pos": {}}
    post = {"generation_tokens_total": 6408.0, "per_pos": {}}
    outs = [c4._fake_stream(1600, 100.0, 0.03) for _ in range(4)]
    res_ok = c4.evaluate_pass(outs, pre, post, 100.0, 150.0, 1600)
    # plain c4 evaluation flags 6408 != 6400; mixed guard must accept it
    reasons = [r for r in res_ok["invalid_reasons"] if not r.startswith("gen_delta=")]
    check("guard accepts gen_delta incl. injected", not any(r.startswith("gen_delta") for r in reasons))

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / f"{NAME}-{c4.utc_stamp()}-c4.json"
        write_excl(p, {"a": 1})
        try:
            write_excl(p, {"a": 2}); ok = False
        except FileExistsError:
            ok = True
        check("O_EXCL: refuses overwrite", ok)

    print(f"self-test: {'OK' if not fails else 'FAILED: ' + ', '.join(fails)}", flush=True)
    return 0 if not fails else 1


# --------------------------------- main ---------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default=c4.BASE, help="serve base URL (default %(default)s)")
    ap.add_argument("--inject-tokens", type=int, default=DEFAULT_INJECT_TOKENS,
                    help="target prompt_tokens of the injected cold prefill (default 16000)")
    ap.add_argument("--inject-delay", type=float, default=DEFAULT_INJECT_DELAY_S,
                    help="seconds after C4 streams start to inject (default 10)")
    ap.add_argument("--cooldown", type=float, default=60.0,
                    help="seconds between baseline and guard passes (default 60)")
    ap.add_argument("--out", metavar="DIR", help="output dir; writes mixedguard-<UTC>-c4.json (O_EXCL)")
    ap.add_argument("--self-test", action="store_true", help="offline validation, no server")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()

    c4.BASE = args.base
    rcp.BASE = args.base

    print(f"[baseline] warming 4x{c4.WARM_TOKENS}...", file=sys.stderr, flush=True)
    c4.run_warmup()
    baseline = c4.run_pass()
    print(f"[baseline] valid={baseline['valid']} steady_agg={baseline['steady_agg_tok_s']} "
          f"max_stall={max_stall_ms(baseline)}ms", file=sys.stderr, flush=True)

    print(f"[guard] cooling {args.cooldown}s...", file=sys.stderr, flush=True)
    time.sleep(args.cooldown)

    print(f"[guard] calibrating ~{args.inject_tokens}-token front-salted injection prompt...",
          file=sys.stderr, flush=True)
    prompt, filler, tok_est = build_injected_prompt(args.inject_tokens)

    print(f"[guard] warming 4x{c4.WARM_TOKENS}...", file=sys.stderr, flush=True)
    c4.run_warmup()
    guard = run_guard_pass(prompt, args.inject_delay)
    guard["injected"]["filler_count"] = filler
    guard["injected"]["tokenize_est"] = tok_est
    print(f"[guard] valid={guard['valid']} steady_agg={guard['steady_agg_tok_s']} "
          f"max_stall={max_stall_ms(guard)}ms injected_ttft={guard['injected']['ttft_s']}s "
          f"cached={guard['injected']['cached_tokens']}", file=sys.stderr, flush=True)

    doc = summarize(baseline, guard)
    doc["config"]["inject_tokens_target"] = args.inject_tokens
    doc["config"]["inject_delay_s"] = args.inject_delay
    print(json.dumps({k: doc[k] for k in doc if k not in ("baseline_pass", "guard_pass")}, indent=1),
          flush=True)
    if args.out:
        p = Path(args.out) / f"{NAME}-{c4.utc_stamp()}-c4.json"
        try:
            write_excl(p, doc)
        except FileExistsError:
            print(f"REFUSED: {p} already exists (O_EXCL) — never overwrite", file=sys.stderr, flush=True)
            return 2
        print(f"WROTE {p}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
