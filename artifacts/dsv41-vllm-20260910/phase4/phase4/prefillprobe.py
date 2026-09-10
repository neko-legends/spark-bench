#!/usr/bin/env python3
"""Cold-prefill probe with UNIQUE prefix per run (defeats prefix cache). Targets given as comma list.
usage: prefillprobe.py <label> 8000,32000,100000 [--seed 1]"""
import json, random, sys, time, urllib.request

BASE = "http://192.168.10.1:8000/v1"
MODEL = "deepseek-v4.1-flash"
WORDS = ("amber basin cedar delta ember fjord garnet harbor iris juniper kestrel lumen meadow nimbus orchid "
         "pylon quartz raven sierra tundra umber vessel willow xenon yarrow zephyr").split()

def filler(n_words, seed):
    rnd = random.Random(seed)
    return " ".join(f"{rnd.choice(WORDS)}{rnd.randint(0, 999)}" for _ in range(n_words))

label = sys.argv[1]
targets = [int(x) for x in sys.argv[2].split(",")]
seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 1
out = {}
for t in targets:
    prompt = f"[prefillprobe {label} {t} s{seed}] " + filler(int(t * 0.55), seed * 100000 + t) + \
             "\n\nReply with the single word OK."
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 4,
            "temperature": 0, "stream": True, "stream_options": {"include_usage": True},
            "chat_template_kwargs": {"thinking": False}}
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"): continue
            data = line[5:].strip()
            if data == "[DONE]": break
            ev = json.loads(data)
            usage = ev.get("usage")
    total = time.time() - t0
    pt = (usage or {}).get("prompt_tokens", 0)
    row = {"target": t, "prompt_tokens": pt, "ttft_s": round(total, 3), "prefill_tok_s": round(pt / total, 1) if total else None}
    out[t] = row
    print(json.dumps(row), flush=True)
json.dump({"label": label, "seed": seed, "rows": list(out.values())},
          open(f"/home/jun/dsv41-vllm/phase4/{label}/prefill-probe.json", "w"), indent=1)
