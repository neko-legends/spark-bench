# GLM-5.3-Flash FP4 (nvidia/GLM-5.3-Flash-FP4-Local) · vLLM (community b12x image) · four Sparks, TP-4 — 2026-10-17

The first bench right after load, same harnesses as the DeepSeek / Nemotron rows (no changed inputs or scoring).

**Engine:** `eugr/spark-vllm-b12x:latest` (digest `sha256:03a95654…3595`, vLLM 0.1.dev21830+g8244d1c44, built 2026-10-15) — the
container the model card requires (its NVFP4 scales use a new compressed format upstream vLLM can't read yet). The card's flags
verbatim (`--quantization modelopt_mixed --load-format b12x`, B12X attention/MoE/linear backends, MTP with 5 draft tokens,
`--max-model-len 500000 --max-num-seqs 4 --max-num-batched-tokens 4096`, fp8 KV, `--gpu-memory-utilization 0.87`), except the
topology: **TP-4 across four Sparks** (the card validates TP-2 on two). KV: 57 GiB per rank = 7.7M tokens. Launcher: [`serve/`](serve/).

Two serving fixes were needed on our fabric, both in the launch, not the model:
1. **RoCE all-reduce.** The b12x RoCE collective ("RoCEnante") takes its GID index from `NCCL_IB_GID_INDEX`, which our fabric sets
   to `-1` (auto) because the RoCEv2 GID index differs per Spark (3 on two, 5 on the other two). It failed with
   `ibv_query_gid: Invalid argument` and fell back to NCCL. The launcher now resolves each Spark's RoCEv2 IPv4 GID and passes
   `B12X_ROCE_GID_INDEX`. Before → after on qbench speed: code 73.3 → 82.0, prose 33.2 → 36.5, 4 streams 75.0 → 81.2 tok/s
   (the before run is kept: `qbench-glm53-fp4-vllm-20261017-pynccl.json`).
2. **Thinking off.** GLM-5.3-Flash's chat template (NVIDIA's and the base model's) has no thinking switch: it always opens
   `<think>` (only `reasoning_effort` low/high/max). qbench and the vision harness run thinking off. The server uses the stock
   template plus one condition ([`serve/chat_template.thinkswitch.jinja`](serve/chat_template.thinkswitch.jinja)): when a request
   sends `enable_thinking: false` or `thinking: false` (and neither true) the generation prompt is `<think></think>`, the form the
   template already uses for past turns without reasoning; this mirrors vLLM's reasoning parser rule exactly. Requests that send
   neither get the stock template byte for byte.

| Area | GLM-5.3-Flash FP4 (vLLM) | DeepSeek V4.1 Flash (TensorFold) | Nemotron 3.5 Super VL (TensorFold) |
| --- | ---: | ---: | ---: |
| Knowledge, MMLU-200 | 88.0 % (176/200) | 88.5 % | 85.0 % |
| Math, GSM8K 0–29 | 100 % | 100 % | 96.7 % |
| Coding, 5 tasks | 80 % | 80 % | 80 % |
| Instruction following, 20 | 90 % | 90 % | 95 % |
| JSON schema / tools / long context to 299K | 100 / 100 / 100 % | 100 / 100 / 100 % | 100 / 100 / 100 % |
| Summary: facts kept / stale / invented numbers | 100 / 0 / 4.2 % | 100 / 0 / 0 % | 100 / 0 / – |
| Vision text, 166 strings | 166/166 | 166/166 | 166/166 |
| Vision shapes 30 (a3 + a5) / objects counted 23 | 28/30 / 0/23 | – / 22/23 | – / 1/23 |
| Code / prose, 1 stream (tok/s) | 82.0 / 36.5 | 155.4 / 72.0 | 185.4 / 94.9 |
| 4 streams, aggregate (tok/s) | 81.2 | 172.1 | 206.8 |
| TTFT, short prompt | 0.25 s | – | – |
| Cold prompt 32K / 131K / 200K tokens | 12.3 / 50.8 / 79.4 s | – / – / 36.8 s | – / – / 48.3 s |

Notes. Vision positions are within 0.7–1.7 px (pixel frame). `k_f_counts` 0/23: GLM's structured read groups repeated objects
("windows: 39 dark blue squares", "~24 trees") instead of listing each, so the counter has nothing to match — the same failure mode
as Nemotron. Four streams do not add throughput over one on this engine (per-stream 40/21/41/22 tok/s); MTP acceptance ≈ 40 %
per draft token (≈ 2 accepted per 5 drafted). Prefill is ~2.5–2.7K tokens/s cold at every size.

Files: `qbench-glm53-fp4-vllm-20261017.json` (283 requests, 0 transport errors) · `qbench-dsv41-vs-glm53.{md,png,svg}` ·
`prefill/` (tools/nemotron/prefill-ladder.py) · `vision/vision-all.json` (window-vision.py: spark-vision `read`, refine on, coords
auto, fresh cache) + the live run's rows (vision-live-run.jsonl).
