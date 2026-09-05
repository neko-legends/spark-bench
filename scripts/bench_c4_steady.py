#!/usr/bin/env python3
"""Steady-state C4 ruler: 4 concurrent 1600-token code streams; server-side gen rate over the steady window.

PROTOCOL FROZEN for comparability with historical numbers (do not change):
- exact CODE prompt text, nonce appended at the END of the prompt (shared prefix
  stays prefix-cache warm — this is the deliberate steady-decode regime),
- temperature 0, thinking off, max_tokens 1600 (measured) / 200 (warmup round).

v2 (2026-09-05, per measurement-audit.REPORT.md Task 3/4):
- per-stream record: t_post, t_first, t_last, all inter-delta gaps,
  finish_reason, usage.prompt_tokens / completion_tokens / cached_tokens
- new metric steady_agg_tok_s = Σct / (min(t_last) − max(t_first)) — the
  all-4-decoding overlap window; the old number is renamed e2e_agg_tok_s and
  both are reported
- TTFT per stream + ITL p50/p95/p99; tokens/bundle = ct / n_deltas
- windowed /metrics counter deltas per pass: spec drafts / draft-tokens /
  accepted + per-position accepted, prefix hits/queries; gauges
  gpu_cache_usage_perc and num_requests_running/waiting sampled at t0
- quiescence gate (running==0 and waiting==0 at t0) and post-window
  Δgeneration_tokens_total == Σct check; violations mark the pass INVALID
  (recorded, never crash)
- assertions: exactly 4 successful streams, all finish_reason=="length",
  Σct == 4×max_tokens — violations mark the pass invalid
- CLI: --passes N (default 1 = old behavior), --cooldown S (default 60),
  --out DIR (required when passes>1) writing <name>-<UTC>-c4.json with O_EXCL
  (never overwrite), --self-test for offline validation

Python 3.10+ stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import threading
import time
import urllib.request
import uuid
from pathlib import Path

BASE = "http://127.0.0.1:18888"
MODEL = "GLM-5.3-Flash-EXL3"
NAME = "c4steady"

# FROZEN ruler text — changing this voids all cross-day comparisons.
CODE = ("Write a complete, idiomatic Python implementation of a binary search tree with "
        "insert, delete, search, traversal, height, docstrings, and tests. Code only. "
        "Add exhaustive tests using pytest, covering edge cases.")

N_STREAMS = 4
WARM_TOKENS = 200
MAX_TOKENS = 1600

# Resolved launcher env recorded into every artifact (None when not exported).
ENV_KEYS = ("ASYNC_SCHEDULING", "DFLASH_TOKENS", "GLM53_MIXED_PREFILL_SMALL_OK",
            "MAX_NUM_BATCHED_TOKENS")

COUNTER_KEYS = (
    "vllm:generation_tokens_total",
    "vllm:spec_decode_num_drafts_total",
    "vllm:spec_decode_num_draft_tokens_total",
    "vllm:spec_decode_num_accepted_tokens_total",
    "vllm:prefix_cache_hits_total",
    "vllm:prefix_cache_queries_total",
)
GAUGE_KEYS = (
    "vllm:gpu_cache_usage_perc",
    "vllm:num_requests_running",
    "vllm:num_requests_waiting",
)
PER_POS_KEY = "vllm:spec_decode_num_accepted_tokens_per_pos_total"


def post(body, timeout=900):
    req = urllib.request.Request(BASE + "/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)


def gen_rate():
    raw = urllib.request.urlopen(BASE + "/metrics", timeout=10).read().decode()
    g = None
    for line in raw.splitlines():
        if line.startswith("vllm:generation_tokens_total"): g = float(line.rsplit(" ", 1)[-1])
    return g


def parse_metrics(raw: str) -> dict:
    """Parse the counters/gauges we window per pass. per_pos is a {position: value} dict."""
    out: dict = {"per_pos": {}}
    for line in raw.splitlines():
        if not line or line.startswith("#"):
            continue
        name, _, val = line.rpartition(" ")
        base = name.split("{", 1)[0].strip()
        try:
            v = float(val)
        except ValueError:
            continue
        if base in COUNTER_KEYS or base in GAUGE_KEYS:
            out[base.split(":", 1)[1]] = v
        elif base == PER_POS_KEY:
            m = re.search(r'position="(\d+)"', name)
            if m:
                out["per_pos"][int(m.group(1))] = v
    return out


def metrics_snapshot() -> dict:
    try:
        raw = urllib.request.urlopen(BASE + "/metrics", timeout=10).read().decode()
        return parse_metrics(raw)
    except Exception:
        return {"per_pos": {}}


def counter_delta(before: dict, after: dict) -> dict:
    d = {}
    for k in COUNTER_KEYS:
        short = k.split(":", 1)[1]
        d[short] = round(after.get(short, 0.0) - before.get(short, 0.0), 1)
    pa, pb = before.get("per_pos", {}), after.get("per_pos", {})
    d["spec_accepted_per_pos"] = {
        str(p): round(pb.get(p, 0.0) - pa.get(p, 0.0), 1) for p in sorted(set(pa) | set(pb))
    }
    return d


def percentile(sorted_vals: list[float], q: float) -> float | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    idx = q * (len(sorted_vals) - 1)
    lo, hi = math.floor(idx), math.ceil(idx)
    if lo == hi:
        return sorted_vals[int(idx)]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (idx - lo)


def itl_stats(gaps: list[float]) -> dict | None:
    if not gaps:
        return None
    s = sorted(gaps)
    return {"n": len(s),
            "p50_ms": round(percentile(s, 0.50) * 1000, 1),
            "p95_ms": round(percentile(s, 0.95) * 1000, 1),
            "p99_ms": round(percentile(s, 0.99) * 1000, 1),
            "max_ms": round(s[-1] * 1000, 1),
            "mean_ms": round(sum(s) / len(s) * 1000, 1)}


def stream_once(prompt, max_tokens):
    """One streamed request (frozen protocol: nonce at END, temp 0, thinking off).

    Returns a full record dict; on failure the dict carries an "error" key
    (never None, so failures are recorded instead of silently dropped).
    """
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt + " nonce=" + uuid.uuid4().hex}],
            "max_tokens": max_tokens, "temperature": 0, "stream": True,
            "stream_options": {"include_usage": True},
            "chat_template_kwargs": {"enable_thinking": False}}
    t_post = time.monotonic()
    t_first = t_last = None
    gaps: list[float] = []
    usage = None
    finish = None
    err = None
    try:
        with post(body) as r:
            for line in r:
                if not line.startswith(b"data:"): continue
                p = line[5:].strip()
                if p == b"[DONE]": break
                try: chunk = json.loads(p)
                except json.JSONDecodeError: continue
                if chunk.get("usage"): usage = chunk["usage"]
                ch = (chunk.get("choices") or [{}])[0]
                d = ch.get("delta") or {}
                if d.get("content") or d.get("reasoning") or d.get("reasoning_content"):
                    now = time.monotonic()
                    if t_first is None:
                        t_first = now
                    else:
                        gaps.append(now - t_last)
                    t_last = now
                if ch.get("finish_reason"): finish = ch["finish_reason"]
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
    if err is None and t_first is None:
        err = "no delta received"
    ct = int((usage or {}).get("completion_tokens") or 0)
    details = (usage or {}).get("prompt_tokens_details") or {}
    rec = {
        "ct": ct,
        "tok_s": None,
        "t_post": t_post,
        "t_first": t_first,
        "t_last": t_last,
        "ttft_s": round(t_first - t_post, 3) if t_first is not None else None,
        "gaps": [round(g, 4) for g in gaps],
        "n_deltas": len(gaps) + 1 if t_first is not None else 0,
        "tokens_per_bundle": round(ct / (len(gaps) + 1), 2) if (t_first is not None and ct > 0) else None,
        "finish_reason": finish,
        "prompt_tokens": int((usage or {}).get("prompt_tokens") or 0),
        "cached_tokens": details.get("cached_tokens") if isinstance(details, dict) else None,
        "completion_tokens": ct,
        "itl_ms": itl_stats(gaps),
        "error": err,
    }
    if err is None and t_first is not None and t_last is not None and ct > 1:
        rec["tok_s"] = round((ct - 1) / (t_last - t_first), 1)
    return rec


def run_warmup():
    """Warm the 4-batch decode shapes with one short round (frozen convention)."""
    short = [None] * 4
    def ws(i): short[i] = stream_once(CODE, WARM_TOKENS)
    ts = [threading.Thread(target=ws, args=(i,)) for i in range(4)]
    [t.start() for t in ts]; [t.join() for t in ts]
    return short


def evaluate_pass(outs, pre, post, t0, t1, max_tokens):
    """Pure evaluation of one C4 pass -> result dict. Violations mark the pass
    invalid (recorded, never raised). Testable offline with synthetic inputs."""
    ok = [r for r in outs if r and not r.get("error") and r.get("tok_s") is not None]
    sum_ct = sum(r["ct"] for r in ok)
    invalid: list[str] = []
    if len(ok) != N_STREAMS:
        invalid.append(f"success_streams={len(ok)}!={N_STREAMS}")
    else:
        bad_fr = [r["finish_reason"] for r in ok if r["finish_reason"] != "length"]
        if bad_fr:
            invalid.append(f"finish_reason!=length:{bad_fr}")
    if sum_ct != N_STREAMS * max_tokens:
        invalid.append(f"sum_ct={sum_ct}!={N_STREAMS * max_tokens}")
    running = pre.get("num_requests_running")
    waiting = pre.get("num_requests_waiting")
    quiescent = running == 0.0 and waiting == 0.0
    if not quiescent:
        invalid.append(f"t0_not_quiescent:running={running},waiting={waiting}")
    g0, g1 = pre.get("generation_tokens_total"), post.get("generation_tokens_total")
    gen_delta = round(g1 - g0, 1) if (g0 is not None and g1 is not None) else None
    if gen_delta is None:
        invalid.append("generation_tokens_total_unavailable")
    elif abs(gen_delta - sum_ct) > 1.0:
        invalid.append(f"gen_delta={gen_delta}!=sum_ct={sum_ct}")

    per = [r["tok_s"] for r in ok]
    window = t1 - t0
    e2e_agg = sum_ct / window if window > 0 else None
    steady = None
    overlap = None
    if len(ok) == N_STREAMS:
        overlap = min(r["t_last"] for r in ok) - max(r["t_first"] for r in ok)
        if overlap is not None and overlap > 0:
            steady = sum_ct / overlap
    return {
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "valid": not invalid,
        "invalid_reasons": invalid,
        "n_success_streams": len(ok),
        "per_stream_tok_s": per,
        "per_stream": outs,
        "ttft_s": [r["ttft_s"] for r in ok],
        "steady_agg_tok_s": round(steady, 1) if steady is not None else None,
        "steady_overlap_s": round(overlap, 1) if overlap is not None else None,
        "e2e_agg_tok_s": round(e2e_agg, 1) if e2e_agg is not None else None,
        "server_gen_rate_tok_s": round(gen_delta / window, 1) if (gen_delta is not None and window > 0) else None,
        "gen_tokens_delta": gen_delta,
        "tokens": sum_ct,
        "window_s": round(window, 1),
        "quiescence_t0": {"num_requests_running": running,
                          "num_requests_waiting": waiting,
                          "gpu_cache_usage_perc": pre.get("gpu_cache_usage_perc"),
                          "ok": quiescent},
        "metrics_delta": counter_delta(pre, post),
    }


def run_pass(max_tokens=MAX_TOKENS):
    """One measured C4 pass (4 x max_tokens concurrent streams)."""
    outs = [None] * 4
    def w(i): outs[i] = stream_once(CODE, max_tokens)
    ts = [threading.Thread(target=w, args=(i,)) for i in range(4)]
    pre = metrics_snapshot()
    t0 = time.monotonic()
    [t.start() for t in ts]; [t.join() for t in ts]
    t1 = time.monotonic()
    postm = metrics_snapshot()
    return evaluate_pass(outs, pre, postm, t0, t1, max_tokens)


def config_block():
    return {
        "ruler": "bench_c4_steady.py v2",
        "model": MODEL,
        "base": BASE,
        "streams": N_STREAMS,
        "max_tokens": MAX_TOKENS,
        "warm_tokens": WARM_TOKENS,
        "temperature": 0,
        "thinking": False,
        "nonce": "appended-at-end (shared prefix deliberately stays cache-warm)",
        "prompt": CODE,
        "prompt_sha256": hashlib.sha256(CODE.encode()).hexdigest(),
        "env": {k: os.environ.get(k) for k in ENV_KEYS},
    }


def utc_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def write_excl(path: Path, obj) -> None:
    """Write JSON with O_EXCL — refuse to overwrite, always."""
    data = json.dumps(obj, indent=1) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w") as f:
        f.write(data)


def out_path(out_dir: str, name: str = NAME) -> Path:
    return Path(out_dir) / f"{name}-{utc_stamp()}-c4.json"


# --------------------------- offline self-test ---------------------------

SAMPLE_METRICS = """# HELP vllm:generation_tokens_total Number of generated tokens.
# TYPE vllm:generation_tokens_total counter
vllm:generation_tokens_total{engine="0",model_name="GLM-5.3-Flash-EXL3"} 100.0
vllm:spec_decode_num_drafts_total{engine="0",model_name="GLM-5.3-Flash-EXL3"} 77.0
vllm:spec_decode_num_draft_tokens_total{engine="0",model_name="GLM-5.3-Flash-EXL3"} 539.0
vllm:spec_decode_num_accepted_tokens_total{engine="0",model_name="GLM-5.3-Flash-EXL3"} 195.0
vllm:spec_decode_num_accepted_tokens_per_pos_total{engine="0",model_name="GLM-5.3-Flash-EXL3",position="0"} 61.0
vllm:spec_decode_num_accepted_tokens_per_pos_total{engine="0",model_name="GLM-5.3-Flash-EXL3",position="6"} 10.0
vllm:prefix_cache_hits_total{engine="0",model_name="GLM-5.3-Flash-EXL3"} 1200.0
vllm:prefix_cache_queries_total{engine="0",model_name="GLM-5.3-Flash-EXL3"} 1240.0
vllm:gpu_cache_usage_perc{engine="0",model_name="GLM-5.3-Flash-EXL3"} 0.42
vllm:num_requests_running{engine="0",model_name="GLM-5.3-Flash-EXL3"} 0.0
vllm:num_requests_waiting{engine="0",model_name="GLM-5.3-Flash-EXL3"} 0.0
"""

def _fake_stream(ct, base_t, rate, finish="length", cached=100):
    """Synthetic per-stream record with evenly spaced gaps starting at base_t."""
    import random
    rng = random.Random(42)
    gaps = [rate + rng.uniform(-0.001, 0.001) for _ in range(ct - 1)]
    t_first = base_t + 0.2
    t_last = t_first + sum(gaps)
    return {"ct": ct, "tok_s": round((ct - 1) / (t_last - t_first), 1),
            "t_post": base_t, "t_first": t_first, "t_last": t_last,
            "ttft_s": round(t_first - base_t, 3), "gaps": [round(g, 4) for g in gaps],
            "n_deltas": ct, "tokens_per_bundle": 1.0, "finish_reason": finish,
            "prompt_tokens": 200, "cached_tokens": cached, "completion_tokens": ct,
            "itl_ms": itl_stats(gaps), "error": None}

def self_test() -> int:
    import tempfile
    fails = []
    def check(name, cond):
        print(("PASS" if cond else "FAIL") + f" {name}", flush=True)
        if not cond: fails.append(name)

    # 1. metrics parsing
    m = parse_metrics(SAMPLE_METRICS)
    check("parse: generation_tokens_total", m.get("generation_tokens_total") == 100.0)
    check("parse: spec drafts", m.get("spec_decode_num_drafts_total") == 77.0)
    check("parse: per_pos", m.get("per_pos") == {0: 61.0, 6: 10.0})
    check("parse: gauges", m.get("num_requests_running") == 0.0 and m.get("gpu_cache_usage_perc") == 0.42)
    m2 = parse_metrics(SAMPLE_METRICS.replace(" 100.0", " 7400.0").replace(" 77.0", " 177.0")
                        .replace('position="0"} 61.0', 'position="0"} 161.0'))
    d = counter_delta(m, m2)
    check("delta: generation", d["generation_tokens_total"] == 7300.0)
    check("delta: per_pos", d["spec_accepted_per_pos"] == {"0": 100.0, "6": 0.0})

    # 2. percentiles
    check("percentile: median of [1,2,3]", percentile([1, 2, 3], 0.5) == 2)
    check("percentile: p95 monotone", (percentile([1] * 10, 0.95) or 0) == 1)
    st = itl_stats([0.01, 0.02, 0.03, 0.1])
    check("itl: p50/p99/max", st["p50_ms"] == 25.0 and st["max_ms"] == 100.0 and st["p99_ms"] >= st["p95_ms"])

    # 3. evaluate_pass: valid synthetic pass
    t0 = 100.0
    outs = [_fake_stream(1600, t0 + i * 0.05, 0.03) for i in range(4)]
    pre = parse_metrics(SAMPLE_METRICS)
    post = parse_metrics(SAMPLE_METRICS.replace(" 100.0", " 6500.0"))
    res = evaluate_pass(outs, pre, post, t0, t0 + 50.0, 1600)
    check("valid pass: ok", res["valid"] and res["n_success_streams"] == 4)
    check("valid pass: sum_ct", res["tokens"] == 6400)
    check("steady_agg computed", res["steady_agg_tok_s"] is not None and res["steady_agg_tok_s"] > 0)
    check("e2e_agg = 6400/50", res["e2e_agg_tok_s"] == 128.0)
    check("steady > e2e (overlap window narrower)", res["steady_agg_tok_s"] >= res["e2e_agg_tok_s"])
    check("gen delta matches sum_ct", "gen_delta" not in json.dumps(res["invalid_reasons"]))

    # 4. invalid: early EOS (the baseline-C bug: Σct < 4×max_tokens)
    outs_bad = [_fake_stream(1600, t0, 0.03) for _ in range(3)] + [_fake_stream(1435, t0, 0.03)]
    res_bad = evaluate_pass(outs_bad, pre, post, t0, t0 + 50.0, 1600)
    check("invalid: early-EOS flagged not crashed", not res_bad["valid"] and
          any("sum_ct" in r for r in res_bad["invalid_reasons"]))

    # 5. invalid: wrong finish_reason
    outs_fr = [_fake_stream(1600, t0, 0.03) for _ in range(3)] + [_fake_stream(1600, t0, 0.03, finish="stop")]
    res_fr = evaluate_pass(outs_fr, pre, post, t0, t0 + 50.0, 1600)
    check("invalid: finish_reason flagged", not res_fr["valid"] and
          any("finish_reason" in r for r in res_fr["invalid_reasons"]))

    # 6. invalid: not quiescent at t0
    pre_busy = dict(pre, num_requests_running=2.0, num_requests_waiting=1.0)
    res_busy = evaluate_pass(outs, pre_busy, post, t0, t0 + 50.0, 1600)
    check("invalid: quiescence gate", not res_busy["valid"] and
          any("quiescent" in r for r in res_busy["invalid_reasons"]))

    # 7. invalid: third-party traffic (gen delta != sum_ct)
    post_noisy = parse_metrics(SAMPLE_METRICS.replace(" 100.0", " 9999.0"))
    res_noisy = evaluate_pass(outs, pre, post_noisy, t0, t0 + 50.0, 1600)
    check("invalid: third-party traffic flagged", not res_noisy["valid"] and
          any("gen_delta" in r for r in res_noisy["invalid_reasons"]))

    # 8. failed stream (thread exception) recorded, not dropped
    outs_none = outs[:3] + [{"error": "URLError: x", "tok_s": None, "ct": 0}]
    res_none = evaluate_pass(outs_none, pre, post, t0, t0 + 50.0, 1600)
    check("invalid: 3-of-4 streams flagged", not res_none["valid"] and
          any("success_streams=3" in r for r in res_none["invalid_reasons"]))

    # 9. JSON serializable
    try:
        json.dumps(res, default=str); ok = True
    except Exception:
        ok = False
    check("result JSON serializable", ok)

    # 10. O_EXCL: second write to same path must fail
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / f"{NAME}-{utc_stamp()}-c4.json"
        write_excl(p, {"a": 1})
        try:
            write_excl(p, {"a": 2}); excl_ok = False
        except FileExistsError:
            excl_ok = True
        check("O_EXCL: refuses overwrite", excl_ok and p.read_text().strip() == '{\n "a": 1\n}')
        import re as _re
        check("filename format <name>-<UTC>-c4.json",
              bool(_re.fullmatch(r"c4steady-\d{8}T\d{6}Z-c4\.json", p.name)))

    print(f"self-test: {'OK' if not fails else 'FAILED: ' + ', '.join(fails)}", flush=True)
    return 0 if not fails else 1


# --------------------------------- main ---------------------------------

def main(argv=None) -> int:
    global BASE
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--passes", type=int, default=1,
                    help="number of measured C4 passes (default 1 = historical behavior)")
    ap.add_argument("--cooldown", type=float, default=60.0,
                    help="seconds between passes (default 60)")
    ap.add_argument("--out", metavar="DIR",
                    help="output directory; writes <name>-<UTC>-c4.json with O_EXCL. "
                         "Required when --passes > 1.")
    ap.add_argument("--name", default=NAME, help="filename stem (default c4steady)")
    ap.add_argument("--base", default=BASE, help="serve base URL (default %(default)s)")
    ap.add_argument("--self-test", action="store_true", help="offline validation, no server")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    if args.passes < 1:
        ap.error("--passes must be >= 1")
    if args.passes > 1 and not args.out:
        ap.error("--out DIR is required when --passes > 1")

    BASE = args.base

    results = []
    for i in range(args.passes):
        print(f"[pass {i + 1}/{args.passes}] warming 4x{WARM_TOKENS}...", file=sys.stderr, flush=True)
        run_warmup()
        res = run_pass()
        results.append(res)
        print(f"[pass {i + 1}/{args.passes}] valid={res['valid']} "
              f"steady_agg={res['steady_agg_tok_s']} e2e_agg={res['e2e_agg_tok_s']} "
              f"tokens={res['tokens']}"
              + (f" invalid={res['invalid_reasons']}" if res["invalid_reasons"] else ""),
              file=sys.stderr, flush=True)
        if i < args.passes - 1:
            time.sleep(args.cooldown)

    cfg = config_block()
    if args.out:
        doc = {"schema": "c4_steady_v2", "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "config": cfg, "passes": results}
        if results:
            doc["summary"] = {
                "n_passes": len(results),
                "n_valid": sum(1 for r in results if r["valid"]),
                "steady_agg_medians": _medians(results),
            }
        p = out_path(args.out, args.name)
        try:
            write_excl(p, doc)
        except FileExistsError:
            print(f"REFUSED: {p} already exists (O_EXCL) — never overwrite; "
                  f"rerun in a moment for a fresh timestamp", file=sys.stderr, flush=True)
            return 2
        print(f"WROTE {p}", flush=True)
    else:
        # historical behavior: single JSON object to stdout
        doc = dict(results[0]) if results else {}
        doc["config"] = cfg
        print(json.dumps(doc, indent=1), flush=True)
    return 0


def _medians(results):
    import statistics
    vals = [r["steady_agg_tok_s"] for r in results if r.get("steady_agg_tok_s") is not None]
    return round(statistics.median(vals), 1) if vals else None


if __name__ == "__main__":
    raise SystemExit(main())
