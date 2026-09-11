#!/usr/bin/env python3
"""Capture a LocalMaxxing-verifiable speed-test run from our local vLLM world.

Run on forge. Never stores the API key (read from $LMX_KEY at runtime).
Modes: --capture (bench + write payload json), --dry-run, --submit.

Verified-run evidence produced: promptSha256 (canonical prompt, no nonce),
promptSample, outputSha256, outputSample, engineTimingsRaw (verbatim usage),
batchSize 1 / concurrency 1, outputTokens >= 256, spec draft/accept counts.
"""
import argparse, hashlib, json, os, re, sys, time, urllib.request

BASE = "http://192.168.10.1:8000"
LMX = "https://www.localmaxxing.com"
OUT = "/home/jun/dsv41-vllm/lmx"
os.makedirs(OUT, exist_ok=True)


def get_json(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)", **(headers or {})})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def post_json(url, body, headers=None, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)", **(headers or {})})
    try:
        return json.load(urllib.request.urlopen(req, timeout=timeout)), 200
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode() or "{}"), e.code


def canonical_prompts():
    ctx = get_json(f"{LMX}/api/agent-context")
    return {c["id"]: c for c in ctx.get("canonicalPrompts", [])}


def stream_chat(prompt, max_tokens, model="deepseek-v4.1-flash"):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": True,
        "stream_options": {"include_usage": True},
        "chat_template_kwargs": {"thinking": False},
    }
    req = urllib.request.Request(f"{BASE}/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
    t0 = time.perf_counter()
    ttft = None
    text = []
    usage = None
    resp = urllib.request.urlopen(req, timeout=1800)
    for raw in resp:
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if chunk.get("usage"):
            usage = chunk["usage"]
        for ch in chunk.get("choices") or []:
            delta = (ch.get("delta") or {}).get("content")
            if delta:
                if ttft is None:
                    ttft = time.perf_counter() - t0
                text.append(delta)
    wall = time.perf_counter() - t0
    return "".join(text), usage or {}, ttft, wall


def spec_counters():
    """Read exact spec-decode counters if the server exposes /metrics."""
    try:
        raw = urllib.request.urlopen(f"{BASE}/metrics", timeout=10).read().decode()
    except Exception:
        return None
    out = {}
    for line in raw.splitlines():
        if line.startswith("#"):
            continue
        m = re.match(r"(vllm:spec_decode_\w+)\{?[^}]*\}?\s+([0-9.eE+]+)", line)
        if m:
            out[m.group(1)] = float(m.group(2))
    return out or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--submit", action="store_true")
    ap.add_argument("--prompt", default="code-v1")
    ap.add_argument("--max-tokens", type=int, default=600)
    ap.add_argument("--payload", default=f"{OUT}/payload.json")
    ap.add_argument("--gpu-power", default="24,23,25,24")
    args = ap.parse_args()

    if args.capture:
        cps = canonical_prompts()
        if args.prompt not in cps:
            sys.exit(f"unknown canonical prompt {args.prompt}; have {list(cps)}")
        cp = cps[args.prompt]
        ptext = cp["text"]
        phash = hashlib.sha256(ptext.encode()).hexdigest()
        assert phash == cp["sha256"], "canonical prompt hash mismatch - do not submit"
        print(f"[capture] {cp['id']} sha256 ok, ~{cp['approxTokens']} tok, minOut {cp['minOutputTokens']}")

        # warmup (methodology: 1-2 throwaway runs)
        stream_chat(ptext, 64)
        stream_chat(ptext, 64)
        before = spec_counters()
        text, usage, ttft, wall = stream_chat(ptext, args.max_tokens)
        after = spec_counters()

        out_tok = usage.get("completion_tokens", 0)
        in_tok = usage.get("prompt_tokens", 0)
        decode_tok_s = (out_tok - 1) / (wall - ttft) if ttft and wall > ttft and out_tok > 1 else None
        prefill_tok_s = in_tok / ttft if ttft else None

        spec = None
        if before and after:
            d_draft = after.get("vllm:spec_decode_num_draft_tokens_total", 0) - before.get("vllm:spec_decode_num_draft_tokens_total", 0)
            d_acc = after.get("vllm:spec_decode_num_accepted_tokens_total", 0) - before.get("vllm:spec_decode_num_accepted_tokens_total", 0)
            if d_draft or d_acc:
                spec = {"draft": int(d_draft), "accepted": int(d_acc)}
        print(f"[capture] out={out_tok} tok, ttft={ttft:.3f}s, decode={decode_tok_s:.1f} tok/s, prefill={prefill_tok_s:.0f} tok/s")
        print(f"[capture] spec counters: {spec}")

        payload = {
            "hfId": "deepseek-ai/DeepSeek-V4.1-Flash",
            "modelRevision": "fb2764a5cf321eaa5070ca8f9e892818f477c16d",
            "hardware": {"hwClass": "UNIFIED", "chipVendor": "NVIDIA", "chipFamily": "GB10",
                         "chipVariant": "GB10 Grace Blackwell", "unifiedMemoryGb": 512,
                         "os": "Ubuntu 24.04 (DGX OS)"},
            "engineName": "vllm",
            "engineVersion": "dsv41-feat e47aa780",
            "engineRepository": "https://github.com/vllm-project/vllm",
            "quantization": "NVFP4",
            "backend": "cuda",
            "contextLength": 430080,
            "batchSize": 1,
            "promptTokens": in_tok,
            "outputTokens": out_tok,
            "prefillTokens": 0,
            "ttftMs": round(ttft * 1000, 1) if ttft else None,
            "tokSOut": round(decode_tok_s, 2) if decode_tok_s else None,
            "tokSPrefill": round(prefill_tok_s, 1) if prefill_tok_s else None,
            "gpuPowerWatts": [float(x) for x in args.gpu_power.split(",")],
            "engineFlags": {
                "commandSnippet": open("/home/jun/launch-dsv41-vllm-tp4.sh").read()[:3900],
                "tensorParallel": 4, "concurrency": 1, "specDecoding": True, "specMethod": "dspark",
                "specNumTokens": 5, "gpuMemUtil": 0.80, "maxRunningSeqs": 8,
                "kvCacheDtype": "fp8", "prefixCaching": True, "chunkedPrefill": True,
            },
            "promptSha256": phash,
            "promptSample": ptext[:2000],
            "outputSha256": hashlib.sha256(text.encode()).hexdigest(),
            "outputSample": text[:3000] + ("\n…\n" + text[-1000:] if len(text) > 4000 else ""),
            "engineTimingsRaw": usage,
            "temperature": 0,
            "notes": ("4x DGX Spark (GB10), TP4 over ConnectX-7 RoCE, one vLLM world on :8000. "
                      "Native FP4 routed experts + FP8 dense + FP8 Engram served from local NVMe per node "
                      "(engram-on-disk patch, tonyd2wild/Kai). DSpark speculative decoding k=5, greedy draft. "
                      "Context 420k. Bench recipe: canonical prompt, temp 0, thinking off, batch 1, after warmup."),
        }
        if spec:
            payload["engineFlags"]["specDraftTokens"] = spec["draft"]
            payload["engineFlags"]["specAcceptedTokens"] = spec["accepted"]
        with open(args.payload, "w") as f:
            json.dump(payload, f, indent=1)
        print(f"[capture] payload -> {args.payload}")

    key = os.environ.get("LMX_KEY")
    if args.dry_run or args.submit:
        if not key:
            sys.exit("LMX_KEY not set")
        body = json.load(open(args.payload))
        if args.dry_run:
            r, code = post_json(f"{LMX}/api/speed-tests/dry-run", body, {"Authorization": f"Bearer {key}"})
            print(json.dumps(r, indent=1)[:2500])
            print("dry-run http", code)
        if args.submit:
            if os.environ.get("LMX_CONFIRM") != "yes":
                sys.exit("set LMX_CONFIRM=yes to actually submit")
            r, code = post_json(f"{LMX}/api/speed-tests", body, {"Authorization": f"Bearer {key}"})
            print("submit http", code)
            print(json.dumps(r, indent=1)[:2000])


if __name__ == "__main__":
    main()
