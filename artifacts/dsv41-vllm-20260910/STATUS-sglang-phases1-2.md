# DSV41 NVMe-engram port — STATUS

## Stage
COMPLETE (all gates pass; server live, spec-off)

## Started
2026-09-10 06:06 PDT

## Last update
2026-09-10 08:30 PDT

## Done
- Stage 1 (all): repo cloned on forge (commit 5a7694d), Dockerfile, sbsa-linux libcudart patch, flash_mla overlay kept, p1 built+smoked+fanned out.
- Stage 2 (all): /home/jun/launch-dsv41-tp4.sh — orchestrator, workers-first, ConnectX env, direct sglang.launch_server. Two launcher bugs fixed en route (preflight `$rank`→`$i` unbound var; ssh log-tail hang — `A; B &` form with trailing foreground echo, see comment in script).
- Stage 3: first boot healthy (no OOM, Engram lines on all 4 ranks, contiguous row partition, 48 shards in 57s/rank, load_weight 411s). mem=0.80, CACHE_GIB=32 → 4GiB/table/rank.
- Stage 4 gates (FINAL, on p2 image + SPEC=0):
  1. Arithmetic 19+23=42: PASS (thinking off honored)
  2. JSON-schema strict output: PASS
  3. Tool call + result round trip: PASS (after detector patch)
  4. corrcheck 7/7: PASS (models, nonempty, temp0 determinism, tool call, tool history, structured JSON, thinking opt-in)
  5. NIAH 32k: 6/6 PASS; 100k: 6/6 PASS (12/12 total)
  6. Vision: PASS (red circle + blue square, correct order, image_tokens=1024)
  7. Memory stability: PASS (389/389 reqs, 4-concurrent 2k-in/1k-out, 304.5s; host RSS flat ±100MB/node, no swap growth; forge swap 738MB→767MB ≈ flat, .2/.3/.4 zero)
- Stage 5 quick numbers (spec-off): C1 2k-in code: TTFT 12.9s, decode 13.2 tok/s; C4 4-concurrent: 13.5 tok/s/stream (aggregate ~54 tok/s), wall 89.5s/1200tok each. NIAH-derived prefill ~200-280 tok/s.

## Patches (all Dockerfile-reproducible in /home/jun/dsv41-port/Dockerfile)
1. adapter/engram_backend.py: sbsa-linux/aarch64-linux libcudart globs + loud failure if none (arm64 GB10).
2. flash_mla_sm120.py: overlay from 0xSero repo kept (64-token extra-source page split + tagged scratch buffers; verified superset of image copy).
3. sglang deepseekv32_detector.py (via patch_detector.py): DSML parameter `string=` attribute made optional — model omits it, upstream silently drops the parameter → empty tool args. Regression-verified all three attr states.

## Blocked/decisions
- **DSpark (speculative decoding) CORRUPTS output on GB10 — run SPEC=0.** Deterministic `</tool_result>` runaway on tool-result continuations and garbage recursion on some chat requests with spec ON (3/3 identical md5 each); identical requests clean with spec OFF (rawgen3 + full tool gate + corrcheck roundtrip). Root cause not localized (SM120 verify path suspected — possibly interacting with the flash_mla overlay or DeepGEMM); needs a dedicated debug session. This is the main correctness risk carried forward. Spec-on also masked the prefill speed we measured. DSpark acceptance stats from the spec-on boot were not retained (container logs replaced on restart).
- Healthcheck badge shows "unhealthy": image default polls port 8010; server is on 8000. Launcher now passes SERVER_PORT=8000 for future boots (current container still shows the stale badge; server is actually healthy per /v1/models).
- is_sm120_supported() already returns True on GB10 cc(12,1) — no patch needed (suspected risk resolved).

## Next command
(none — handoff complete; REPORT.md written)

## Phase 2 (SGLang perf — closed by Depths 09:52, worker stopped before writing this)

### Done
- P2.1 DSpark corruption matrix (deterministic tool-result-continuation repro, temp 0, raw /generate ×3 per config; artifacts in forge:/home/jun/dsv41-port/p2/repro/):
  - stock spec-on (bs5): corrupt — `</parameter>` runaway after emitting correct value
  - `--disable-cuda-graph-padding`: corrupt, byte-identical
  - `--speculative-dspark-align-verify-tokens-to-graph-tier`: corrupt, byte-identical
  - block-size 4: corrupt, byte-identical
  - SWA bounded-replay off (bs4): corrupt — `<tool_result>{"value":42}</tool_result>` runaway variant
  - eager + spec: probe timed out (eager too slow), inconclusive
  - Speed when spec-on (before corruption check): 39–46 tok/s C1, accept len 3.0–4.7
- P2.2 parallel row_store: draft rewritten row_store.cpp (7605B) + bench_row_store.py written to this cwd but never rebuilt/tested — INCOMPLETE, do not treat as done. Kept for the follow-up worker.
- Clocks verified healthy: 2.18–2.19 GHz sustained on all 4 nodes (2200 lock service active). BUT see Tony's issue #1: GB10 hidden fast/slow state invisible to nvidia-smi (GEMV 70 vs 230 GB/s); our power draw read 18–21 W under 85–95% util — unverified whether we were in slow state; gpuflip probe queued in phase-3 handoff.

### Decisions
- SGLang lane frozen at `local/dsv41-gb10:p2` SPEC=0 (correct fallback, 13.2–13.5 tok/s). Relaunch: `SPEC=0 bash /home/jun/launch-dsv41-tp4.sh`.
- Engine pivot to vLLM approved by Jun (09:25): "use best of everything, use vllm." Worker: depths-dsv41-vllm-20260910.
- Bug report contents: 6-config matrix + artifacts above + suspicion pointer at dsv4 DSpark verify path / compress-ring write-plan on SM121 (cf. closed PR #33872 family); retest on post-#38879 build before filing.
- Follow-up worker (not spawned): DSML parser upstream issue+PR prep; prompt-length sweep; SGLang post-#38879 retest.
