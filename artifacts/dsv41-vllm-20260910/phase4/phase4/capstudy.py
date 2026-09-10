#!/usr/bin/env python3
"""Phase-4 sequence cap study at 420k: C1,2,4,6,8 with ~2k-in/256-out and C1,2,4 with ~100k-in/256-out.
Per-stream + aggregate + TTFT + KV usage (from /metrics gauge before/after each level).
usage: capstudy.py [--base http://192.168.10.1:8000/v1] [--model deepseek-v4.1-flash] [--out capstudy.json]"""
import argparse, json, statistics as st, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys_prompt = ("Write a complete, idiomatic Python implementation of a binary search tree with "
              "insert, delete, search, traversal, height, docstrings, and tests. Code only.")
FILLER_WORDS = ("alpha basin cedar delta ember fjord garnet harbor iris juniper kestrel lumen meadow nimbus orchid "
                "pylon quartz raven sierra tundra umber vessel willow xenon yarrow zephyr").split()
import random
def filler(n_words, seed):
    rnd = random.Random(seed)
    return " ".join(f"{rnd.choice(FILLER_WORDS)}{rnd.randint(0, 999)}" for _ in range(n_words))

def kv_usage(base):
    txt = urllib.request.urlopen(base.replace("/v1", "") + "/metrics", timeout=10).read().decode()
    for line in txt.splitlines():
        if line.startswith("vllm:gpu_cache_usage_perc{") or line.startswith("vllm:gpu_cache_usage_perc "):
            return float(line.rsplit(" ", 1)[-1])
    return None

def stream_chat(base, model, prompt, max_tokens, timeout=1800):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens,
            "temperature": 0, "stream": True, "stream_options": {"include_usage": True},
            "chat_template_kwargs": {"thinking": False}}
    req = urllib.request.Request(base + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time(); ttft = None; usage = None
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"): continue
            data = line[5:].strip()
            if data == "[DONE]": break
            ev = json.loads(data)
            if ev.get("usage"): usage = ev["usage"]
            for ch in ev.get("choices") or []:
                if (ch.get("delta") or {}).get("content") and ttft is None:
                    ttft = time.time() - t0
    total = time.time() - t0
    ct = (usage or {}).get("completion_tokens", 0); pt = (usage or {}).get("prompt_tokens", 0)
    dec = (ct - 1) / (total - ttft) if (ttft is not None and ct > 1) else None
    return {"ttft_s": round(ttft, 3) if ttft else None, "completion_tokens": ct, "prompt_tokens": pt,
            "decode_tok_s": round(dec, 2) if dec else None}

def run_level(base, model, prompt, c, timeout=1800):
    barrier = threading.Barrier(c)
    def one(i):
        p = f"[capstudy c{c} s{i}] " + prompt
        barrier.wait()
        return stream_chat(base, model, p, 256, timeout)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=c) as ex:
        res = list(ex.map(one, range(c)))
    wall = time.time() - t0
    toks = sum(r["completion_tokens"] for r in res)
    decs = [r["decode_tok_s"] for r in res if r["decode_tok_s"]]
    ttfts = [r["ttft_s"] for r in res if r["ttft_s"]]
    return {"c": c, "prompt_tokens": res[0]["prompt_tokens"], "agg_tok_s": round(toks / wall, 2),
            "per_stream_median": st.median(decs) if decs else None,
            "per_stream_min": min(decs) if decs else None,
            "ttft_mean_s": round(st.mean(ttfts), 3) if ttfts else None,
            "kv_before": None, "kv_after": None}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://192.168.10.1:8000/v1")
    ap.add_argument("--model", default="deepseek-v4.1-flash")
    ap.add_argument("--out", default="/home/jun/dsv41-vllm/phase4/capstudy.json")
    a = ap.parse_args()
    rows = []
    # calibrate filler words per token for ~2k prompt
    probe = stream_chat(a.base, a.model, filler(1000, 42), 1)
    per_word = probe["prompt_tokens"] / 1000.0
    print(f"calibration: {per_word:.3f} tok/word", flush=True)
    p2k = "Read the following operations log, then do the task after it.\n\n" + \
          filler(int(2000 / per_word), 7) + "\n\nTASK: " + sys_prompt
    p100k = "Read the following operations log, then do the task after it.\n\n" + \
            filler(int(100000 / per_word), 8) + "\n\nTASK: " + sys_prompt
    for c in [1, 2, 4, 6, 8]:
        kv0 = kv_usage(a.base)
        r = run_level(a.base, a.model, p2k, c)
        r["kv_before"] = kv0; r["kv_after"] = kv_usage(a.base)
        rows.append(r); print(json.dumps(r), flush=True)
    for c in [1, 2, 4]:
        kv0 = kv_usage(a.base)
        r = run_level(a.base, a.model, p100k, c, timeout=3600)
        r["kv_before"] = kv0; r["kv_after"] = kv_usage(a.base)
        rows.append(r); print(json.dumps(r), flush=True)
    json.dump(rows, open(a.out, "w"), indent=1)
    print("wrote", a.out)

if __name__ == "__main__":
    main()
