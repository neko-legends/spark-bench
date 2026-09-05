#!/usr/bin/env python3
"""C1 decode bench (Aug-28 protocol) + C4 aggregate + spec counters + thinking-toggle prefix check.

Decode tok/s = (completion_tokens - 1) / (last-delta-time - first-delta-time),
counting content + reasoning + reasoning_content delta keys (this vLLM build
streams reasoning separately). Usage-counted, temp 0, streamed.

v2 (2026-09-05, per measurement-audit.REPORT.md):
- real ttft_s = t_first - t_post (was hardcoded None — dead in every artifact)
- finish_reason captured per run (length vs EOS finally distinguishable)
- thinking-toggle prefix check switched from global prefix-cache counters
  (which read 0.0 in both committed runs) to per-request
  usage.prompt_tokens_details.cached_tokens on streamed requests
- windowed spec-counter deltas per phase (warmup / each C1 cell / C4 / toggle)
  instead of one boot-cumulative end-only snapshot; per-position acceptance
  included
- --runs N (default 3 = old behavior) with mean/stdev alongside median
- --out PATH parameter; O_EXCL, never overwrites. Without --out the old
  dated path is kept ONLY with a loud deprecation warning — pass --out.

Python 3.10+ stdlib only.
"""
from __future__ import annotations
import argparse, json, os, re, statistics, sys, time, uuid, threading, urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:18888"
MODEL = "GLM-5.3-Flash-EXL3"
DEPRECATED_DEFAULT_OUT = Path("/home/jun/glm-bench-results/bench_decode_2026-09-02.json")

PROMPTS = {
    "code": ("Write a complete, idiomatic Python implementation of a binary search "
             "tree with insert, delete, search, traversal, height, docstrings, and "
             "tests. Code only."),
    "structured": ("Count from 1 to 200. Output only the numbers, separated by "
                   "spaces. No other text."),
    "math": ("A water tank is filled by two pipes. Pipe A alone fills it in 6 "
             "hours, pipe B alone fills it in 4 hours. Pipe C can drain the full tank in "
             "12 hours. All three are opened at once. How long until the tank is "
             "full? Show every step of your work, then state the answer."),
    "prose": ("Write a detailed step-by-step explanation of how a hash map works, "
              "including collision handling, resizing, and time complexity. "
              "Be thorough."),
}

COUNTER_KEYS = ("vllm:spec_decode_num_drafts_total",
                "vllm:spec_decode_num_draft_tokens_total",
                "vllm:spec_decode_num_accepted_tokens_total",
                "vllm:prefix_cache_hits_total",
                "vllm:prefix_cache_queries_total",
                "vllm:generation_tokens_total")
PER_POS_KEY = "vllm:spec_decode_num_accepted_tokens_per_pos_total"


def post(body, timeout=600):
    req = urllib.request.Request(BASE + "/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)


def stream_once(prompt, thinking, max_tokens=400):
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt + " nonce=" + uuid.uuid4().hex}],
            "max_tokens": max_tokens, "temperature": 0, "stream": True,
            "stream_options": {"include_usage": True},
            "chat_template_kwargs": {"enable_thinking": thinking}}
    t_post = time.monotonic()
    t_first = t_last = None; usage = None; finish = None
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
            if ch.get("finish_reason"): finish = ch["finish_reason"]
    ct = int((usage or {}).get("completion_tokens") or 0)
    if not t_first or ct < 2: return None
    dur = t_last - t_first
    details = (usage or {}).get("prompt_tokens_details") or {}
    return {"completion_tokens": ct, "decode_s": round(dur, 3),
            "tok_s": round((ct - 1) / dur, 1),
            "ttft_s": round(t_first - t_post, 3),
            "finish_reason": finish,
            "prompt_tokens": int((usage or {}).get("prompt_tokens") or 0),
            "cached_tokens": details.get("cached_tokens") if isinstance(details, dict) else None}


def parse_metrics(raw: str) -> dict:
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
        if base in COUNTER_KEYS:
            out[base] = v
        elif base == PER_POS_KEY:
            m = re.search(r'position="(\d+)"', name)
            if m:
                out["per_pos"][int(m.group(1))] = v
    return out


def spec_counters() -> dict:
    """Full snapshot incl. per-position acceptance (windowed per phase)."""
    raw = urllib.request.urlopen(BASE + "/metrics", timeout=10).read().decode()
    return parse_metrics(raw)


def spec_delta(before: dict, after: dict) -> dict:
    d = {k: round(after.get(k, 0.0) - before.get(k, 0.0), 1) for k in COUNTER_KEYS}
    pa, pb = before.get("per_pos", {}), after.get("per_pos", {})
    d["spec_accepted_per_pos"] = {str(p): round(pb.get(p, 0.0) - pa.get(p, 0.0), 1)
                                  for p in sorted(set(pa) | set(pb))}
    return d


def write_excl(path: Path, obj) -> None:
    data = json.dumps(obj, indent=1) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w") as f:
        f.write(data)


def cell_stats(runs):
    ok = [r for r in runs if r]
    if not ok:
        return {"median_tok_s": None, "mean_tok_s": None, "stdev_tok_s": None,
                "n_ok": 0, "n_runs": len(runs)}
    toks = [r["tok_s"] for r in ok]
    sd = statistics.stdev(toks) if len(toks) > 1 else 0.0
    return {"median_tok_s": round(statistics.median(toks), 1),
            "mean_tok_s": round(statistics.mean(toks), 1),
            "stdev_tok_s": round(sd, 1),
            "n_ok": len(ok), "n_runs": len(runs)}


def main(argv=None) -> int:
    global BASE
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", metavar="PATH",
                    help="output JSON path (O_EXCL — refuses to overwrite). "
                         "Strongly recommended; without it the deprecated 2026-09-02 "
                         "path is used with a loud warning.")
    ap.add_argument("--runs", type=int, default=3,
                    help="runs per C1 cell (default 3 = historical; use >=5 for mean±sd)")
    ap.add_argument("--base", default=BASE, help="serve base URL (default %(default)s)")
    ap.add_argument("--self-test", action="store_true", help="offline validation, no server")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()

    BASE = args.base
    results = {"model": MODEL, "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "schema": "bench_decode_v2",
               "c1": {}, "c4": {}, "thinking_toggle_prefix": {}, "spec_phases": {}}

    print("warmup (3 short requests)...", flush=True)
    ph0 = spec_counters()
    for i in range(3):
        stream_once(PROMPTS["structured"][:80], False, max_tokens=32)
    results["spec_phases"]["warmup"] = spec_delta(ph0, spec_counters())

    for cat, prompt in PROMPTS.items():
        for thinking in (True, False):
            ph_a = spec_counters()
            runs = [stream_once(prompt, thinking) for _ in range(args.runs)]
            ph_b = spec_counters()
            stats = cell_stats(runs)
            results["c1"][f"{cat}_{'thinkon' if thinking else 'thinkoff'}"] = {**stats, "runs": runs}
            results["spec_phases"][f"c1_{cat}_{'thinkon' if thinking else 'thinkoff'}"] = spec_delta(ph_a, ph_b)
            print(f"C1 {cat} think={'on ' if thinking else 'off'}: median {stats['median_tok_s']} "
                  f"tok/s mean {stats['mean_tok_s']} ± {stats['stdev_tok_s']} "
                  f"(runs: {[r['tok_s'] for r in runs if r]}, "
                  f"finish: {[r['finish_reason'] for r in runs if r]})", flush=True)

    # ---- C4: 4 concurrent identical-shape code requests, thinking off ----
    print("C4 aggregate (4 concurrent, think off)...", flush=True)
    ph_a = spec_counters()
    outs = [None] * 4
    def worker(i):
        outs[i] = stream_once(PROMPTS["code"], False)
    t0 = time.monotonic()
    ths = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    [t.start() for t in ths]; [t.join() for t in ths]
    total_tok = sum(r["completion_tokens"] for r in outs if r)
    wall = time.monotonic() - t0
    results["spec_phases"]["c4"] = spec_delta(ph_a, spec_counters())
    ok4 = [r for r in outs if r]
    results["c4"] = {"aggregate_tok_s": round(total_tok / wall, 1), "wall_s": round(wall, 1),
                     "total_tokens": total_tok, "per_stream": [r["tok_s"] for r in ok4],
                     "finish_reasons": [r["finish_reason"] for r in ok4],
                     "ttft_s": [r["ttft_s"] for r in ok4]}
    print(f"C4: {results['c4']['aggregate_tok_s']} tok/s aggregate over {wall:.0f}s "
          f"(finish: {results['c4']['finish_reasons']})", flush=True)

    # ---- thinking-toggle prefix-cache check (template fix proof) ----
    # v2: per-request cached_tokens from streamed usage instead of global
    # prefix-cache counters (the old method read 0.0 hits in both committed
    # runs and could not distinguish cold vs warm per request).
    print("thinking-toggle prefix-cache check (per-request cached_tokens)...", flush=True)
    ph_a = spec_counters()
    sysm = {"role": "system", "content": "You are a helpful assistant. " + ("filler " * 1200)}
    base_hist = [sysm, {"role": "user", "content": "What is 2+2?"}]

    def chat(hist, thinking, mt=8):
        return stream_once_hist(hist, thinking, mt)

    r1 = chat(base_hist, True)                     # cold, thinking on
    r2 = chat(base_hist + [{"role": "assistant", "content": ((r1 or {}).get("text") or "OK")},
                           {"role": "user", "content": "Now what is 3+3?"}], False)  # toggle off
    results["spec_phases"]["thinking_toggle"] = spec_delta(ph_a, spec_counters())
    cold_ok = r1 is not None and r1.get("cached_tokens") is not None
    tog_ok = r2 is not None and r2.get("cached_tokens") is not None
    ratio = None
    if tog_ok and r2.get("prompt_tokens"):
        ratio = round(r2["cached_tokens"] / r2["prompt_tokens"], 3)
    results["thinking_toggle_prefix"] = {
        "method": "per-request usage.prompt_tokens_details.cached_tokens (streamed)",
        "cold": _pick(r1), "toggle": _pick(r2), "toggle_cached_ratio": ratio}
    print(f"toggle cached_tokens: cold={_pick(r1)['cached_tokens']} "
          f"toggle={_pick(r2)['cached_tokens']}/{_pick(r2)['prompt_tokens']} "
          f"ratio={ratio}", flush=True)

    spec = spec_counters()
    results["spec_counters_end"] = spec

    if args.out:
        out_path = Path(args.out)
    else:
        out_path = DEPRECATED_DEFAULT_OUT
        msg = (f"DEPRECATED: --out not given; writing the old hardcoded path {out_path}. "
               f"This path belongs to the 2026-09-02 run and must not be reused — "
               f"pass --out <timestamped path> instead.")
        print("!" * 8 + " " + msg, file=sys.stderr, flush=True)
        results["deprecation_warning"] = msg
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write_excl(out_path, results)
    except FileExistsError:
        print(f"REFUSED: {out_path} already exists (O_EXCL) — never overwrite; "
              f"pass --out with a fresh path", file=sys.stderr, flush=True)
        return 2
    print(f"WROTE {out_path}", flush=True)
    return 0


def _pick(r):
    if not r:
        return {"error": "run failed (no usage)"}
    return {"prompt_tokens": r.get("prompt_tokens"),
            "cached_tokens": r.get("cached_tokens"),
            "ttft_s": r.get("ttft_s"),
            "finish_reason": r.get("finish_reason")}


def stream_once_hist(hist, thinking, max_tokens):
    """stream_once for a full message history (used by the toggle check)."""
    body = {"model": MODEL, "messages": hist, "max_tokens": max_tokens,
            "temperature": 0, "stream": True,
            "stream_options": {"include_usage": True},
            "chat_template_kwargs": {"enable_thinking": thinking}}
    t_post = time.monotonic()
    t_first = t_last = None; usage = None; finish = None; text = []
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
            if d.get("content"):
                text.append(d["content"])
            if d.get("content") or d.get("reasoning") or d.get("reasoning_content"):
                now = time.monotonic()
                if t_first is None: t_first = now
                t_last = now
            if ch.get("finish_reason"): finish = ch["finish_reason"]
    ct = int((usage or {}).get("completion_tokens") or 0)
    if not t_first or ct < 1:
        return None
    details = (usage or {}).get("prompt_tokens_details") or {}
    return {"completion_tokens": ct, "tok_s": round((ct - 1) / (t_last - t_first), 1) if ct > 1 else None,
            "ttft_s": round(t_first - t_post, 3), "finish_reason": finish,
            "prompt_tokens": int((usage or {}).get("prompt_tokens") or 0),
            "cached_tokens": details.get("cached_tokens") if isinstance(details, dict) else None,
            "text": "".join(text)}


# --------------------------- offline self-test ---------------------------

def self_test() -> int:
    import tempfile
    fails = []
    def check(name, cond):
        print(("PASS" if cond else "FAIL") + f" {name}", flush=True)
        if not cond: fails.append(name)

    sample = """# HELP vllm:spec_decode_num_drafts_total Number of spec decoding drafts.
vllm:spec_decode_num_drafts_total{engine="0"} 10.0
vllm:spec_decode_num_accepted_tokens_per_pos_total{engine="0",position="3"} 5.0
vllm:generation_tokens_total 100.0
vllm:prefix_cache_hits_total 1.0
vllm:prefix_cache_queries_total 2.0
"""
    m = parse_metrics(sample)
    check("parse: drafts", m["vllm:spec_decode_num_drafts_total"] == 10.0)
    check("parse: per_pos", m["per_pos"] == {3: 5.0})
    d = spec_delta(m, dict(m, **{"vllm:spec_decode_num_drafts_total": 25.0}))
    check("delta: drafts", d["vllm:spec_decode_num_drafts_total"] == 15.0)
    check("delta: per_pos empty", d["spec_accepted_per_pos"] == {"3": 0.0})

    stats = cell_stats([{"tok_s": 10.0}, {"tok_s": 20.0}, {"tok_s": 30.0}, None])
    check("cell_stats: mean/sd/n", stats["mean_tok_s"] == 20.0 and stats["stdev_tok_s"] == 10.0
          and stats["n_ok"] == 3 and stats["n_runs"] == 4)
    stats1 = cell_stats([{"tok_s": 10.0}])
    check("cell_stats: single run sd=0", stats1["stdev_tok_s"] == 0.0)

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "out.json"
        write_excl(p, {"a": 1})
        try:
            write_excl(p, {"a": 2}); ok = False
        except FileExistsError:
            ok = True
        check("O_EXCL: refuses overwrite", ok)

    print(f"self-test: {'OK' if not fails else 'FAILED: ' + ', '.join(fails)}", flush=True)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
