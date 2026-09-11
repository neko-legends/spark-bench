# DeepSeek-V4.1-Flash on 4× DGX Spark — documentation index

Everything needed to write the public spark-bench section for this model, plus the evidence
behind every number. Snapshot taken 2026-09-10 evening, mid-campaign (phase 4b running).

**Status when this index was written:** vLLM TP4 world live at 420k context, DSpark k=5 with
greedy draft (accepted arm), all correctness gates passing. SGLang lane frozen correct-but-slow
(spec-off). Tuning campaign continuing (B4/B5/B7/B8/B9/B10 + Stage C combo).

## Where the story lives

| file | what it is |
|---|---|
| `STATUS.md` | stage-by-stage log, all four phases (SGLang port, SGLang perf/closed, vLLM phase 3, phase 4 tuning). Authoritative chronology. |
| `STATUS-phase3.md`, `STATUS-phase3-final.md` | phase-3 snapshots as the world went 131k → 300k |
| `STATUS-sglang-phases1-2.md` | SGLang lane: boot, gates, the 6-config DSpark corruption matrix, closure |
| `REPORT-phase3.md` | phase-3 worker report (vLLM world up, DSpark clean, benches) |
| `HANDOFF-phase3.md` | the vLLM port plan (what was asked, constraints, sources) |
| `HANDOFF-phase4.md` | the tuning-campaign design: method, arm list, accept/reject rules, backup cadence |
| `HANDOFF-phase4b-resume.md` | post-reboot recovery plan; remaining arms + Stage C + LocalMaxxing capture |
| `CHAMPION.env` | the current best config, exact env to relaunch |
| `README.md` | the original artifact README (attribution + lane summary) |

## Reproduce it

| path | what |
|---|---|
| `launch/launch-dsv41-vllm-tp4.sh` | TP4 launcher (Tony boot-10 config on our fabric; disarmed boot → API → spec gate → arm) |
| `patches/` | the 8 bind-mounted vLLM patch files (`mounts.txt` + md5s match tonyd2wild `patch/README.md` @ ca662ac) |
| `Dockerfile`, `patch_detector.py`, `sglang-lane/` | SGLang fallback lane (dev-dsv41 + 0xSero engram adapter + DSML parser fix) |
| `sglang-lane/dspark-corruption-repro/` | the 6-config corruption matrix (all corrupt, byte-identical or same family) — evidence for the upstream bug report |
| `lmx-capture.py` | LocalMaxxing capture harness (canonical-prompt hash assertion, warmup, streaming TTFT, exact spec counters from /metrics, dry-run/submit; key runtime-only) |

Key upstream pins (recorded in STATUS): Tony repo `ca662ac`, vLLM `dsv41-feat` `e47aa780`,
base image `vllm/vllm-openai:nightly-8a728663`, FlashInfer `0.7.0rc1` `07869c61`,
model `deepseek-ai/DeepSeek-V4.1-Flash` @ `fb2764a5`, SGLang image `lmsysorg/sglang:dev-dsv41`,
Sero adapter commit `5a7694d9`.

## Measurements

| path | what |
|---|---|
| `bench/` | phase-3 benches (131k + 300k), Tony prompt-set tables, `bench-decode`/`bench-depth` logs, telemetry CSVs |
| `phase4/` | per-arm data: `capstudy.json` (sequence cap), `drift-boot2` (boot-to-boot drift band), `b3-greedy/` (accepted, +30% C1), `b6-fusion/` (rejected), shortbench logs, `armmetrics.py`, `shortbench.sh`, `gates.py` |
| `gpuflip/` | GB10 fast/slow-state probes per node (preboot + mid-campaign) — all fast, zero flips with the clock lock active |
| `nccl/` | 4-node all-reduce latency (60 KB p50 66 µs; 4.4–5.7 ms/step collective cost) |
| `self-analysis-2026-09-10.md` | V4.1's own engineering dig on making itself faster (rankings, bimodality hypotheses, 6 new levers, risks) — quoted material for the writeup |

## Headline numbers so far (all at 420k, batch 1, temp 0, thinking off, after warmup)

| metric | value | note |
|---|---:|---|
| C1 per-stream decode (coding) | **70.8 tok/s** | greedy draft; was 54.5 probabilistic |
| C1 per-stream decode (math) | **72.9 tok/s** | +36% from greedy draft |
| C1 per-stream decode (prose) | 29.1 tok/s | +31%; prose remains the weak category |
| C6 aggregate | 132 tok/s | parity with tonyd2wild boot-10 (131.86) on the same hardware |
| cold prefill | 1.0–1.5k tok/s | 8k/32k/100k prompts |
| KV pool | 1,374,757 tokens @ 300k (4.58×) / 420k config | gmu 0.80 |
| DSpark acceptance | 4.12–4.36 mean tok/step, 67% rate | near 6 on counting/tables, ~2 on prose |
| sequence cap | 4 | C4 = 56% of C1 per-stream, C8 = 27%; dash updated to maxSeqs 4 |

Comparison anchors: our V4 Flash on the same fabric did 136 C1 best-case / 66–93 at real chat
depth / 182 at C4; tonyd2wild's V4.1 boot-10 (same 4×GB10) did C1 code 73.8, mean 43, C6 132.

## Still to add when the campaign finishes

1. **Stage C combo verification** (A/B/A at 420k) and the final arm table → `phase4/RESULTS.md`.
2. **Remaining arm verdicts**: B7 batched-tokens, B4 clock unlock, B5 MoE/prefill backend, B8 DeepSelect, B9 NCCL sweep, B10 engram threads.
3. **LocalMaxxing Verified runs** (`code-v1`, `reasoning-v1`) — payloads + submission receipts.
4. **The public README section** — "DeepSeek V4.1 Flash — 4× DGX Spark", same honest-map protocol as V4 Flash, with the dashboard screenshot (`docs/images/dsv41-vllm-tp4-dashboard-2026-09-10.webp`) and attribution.

## Attribution (carry into the publish)

tonyd2wild + Kai (vLLM recipe, engram-on-disk, SM12x pages, GPU slow-state finding), 0xSero
(SGLang engram adapter, SM120 attention fix), LMSYS (SGLang `dev-dsv41`), the vLLM team
(`dsv41-feat`), DeepSeek (model). Our contributions: the arm64/multi-node port, all-local
weights, greedy-draft finding, the SGLang DSpark corruption matrix, the DSML parser bug, and
whatever the remaining arms land.

## Screenshots (for the public README section)

| file | use |
|---|---|
| `docs/images/dsv41-vllm-tp4-dashboard-2026-09-10.webp` | live DGX-dash view: 81 tok/s single stream, 300 peak, all four nodes, model deepseek-v4.1-flash |
| `docs/images/dsv41-vllm-tp4-champion-table-2026-09-10.webp` | the champion-stats table (config + throughput + per-category + speculation + prefill) — legible README "results" image |
| `docs/images/dsv41-vllm-tp4-x-card-2026-09-10.png` | purpose-built 1600×900 result card (used in the README and the X post). Source SVG: `artifacts/dsv41-vllm-20260910/x-card.svg` |
