#!/usr/bin/env python3
"""Extract arm-bench key metrics from a phase4 <dir>: C1/C4 per-stream coding/math/prose per rep,
prefill 8k/32k per rep, ttft2k, bench-decode distribution, accept summary, 100k prefill."""
import json, sys, glob, statistics as st, re, os

d = sys.argv[1]
def get(path):
    try: return json.load(open(os.path.join(d, path)))
    except Exception: return None

rows = []
for rep in sorted(glob.glob(os.path.join(d, "bench-*-rep*.json"))):
    j = get(os.path.basename(rep))
    if not j: continue
    r = re.search(r"rep(\d+)", rep).group(1)
    for c in [1, 4]:
        for cat in ["coding", "math", "prose"]:
            b = next((b for b in j["batches"] if b["c"] == c and b["category"] == cat), None)
            if b: rows.append({"rep": r, "c": c, "cat": cat, "per": b["per_stream_tok_s"], "agg": b["agg_tok_s"]})
    for p in j.get("prefill", []):
        rows.append({"rep": r, "c": 0, "cat": f"prefill{p['target']}", "per": p["prefill_tok_s"], "agg": p["ttft_s"]})
ttft2k = get("bench-%s-ttft2k.json" % os.path.basename(d).replace("drift-boot2", "drift-boot2"))
for f in glob.glob(os.path.join(d, "*ttft2k.json")):
    j = json.load(open(f))
    b = next((b for b in j["batches"] if b["c"] == 1), None)
    if b: rows.append({"rep": 0, "c": 1, "cat": "ttft2k_s", "per": b["ttft_mean_s"], "agg": None})

# medians across reps
med = {}
for c in [1, 4]:
    for cat in ["coding", "math", "prose"]:
        xs = [r["per"] for r in rows if r["c"] == c and r["cat"] == cat]
        if xs: med[f"C{c}_{cat}_per_median"] = st.median(xs); med[f"C{c}_{cat}_per_reps"] = xs
for tgt in [8000, 32000]:
    xs = [r["per"] for r in rows if r["cat"] == f"prefill{tgt}"]
    if xs: med[f"prefill{tgt}_tok_s_median"] = st.median(xs); med[f"prefill{tgt}_reps"] = xs

# bench-decode
bd = open(os.path.join(d, "bench-decode.log")).read() if os.path.exists(os.path.join(d, "bench-decode.log")) else ""
m = re.search(r'"trials": \[([^\]]*)\]', bd)
if m:
    trials = [float(x) for x in m.group(1).replace("\n", "").split(",") if x.strip()]
    med["bench_decode_trials"] = trials
    med["bench_decode_median"] = st.median(trials) if trials else None
    med["bench_decode_min"] = min(trials) if trials else None
acc = get("accept-summary.json")
if acc: med["accept"] = acc
m100 = re.search(r'\{.*\}', open(os.path.join(d, "prefill-100k.log")).read()) if os.path.exists(os.path.join(d, "prefill-100k.log")) else None
if m100:
    try: med["prefill100k"] = json.loads(m100.group(0))
    except Exception: pass
print(json.dumps(med, indent=1))
