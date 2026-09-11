# DSV41 vLLM Phase 4 + 4b — RESULTS

Host: 4x DGX Spark (GB10), TP4 over ConnectX-7 RoCE. Engine: vLLM dsv41-feat `e47aa780` (`local/vllm-dsv41:overlay5`).
Shipping context 420k (`MAXLEN=430080`, GMU 0.80, block 128). Temp 0, thinking off. One variable at a time vs champion; accept only if median gain > 3% beyond boot-to-boot drift AND gates pass.

## Arm table

| arm | knob | median C1 code | C1 prose | C4 coding agg | prefill@32k tok/s | accept len | verdict |
|---|---|---|---|---|---|---|---|
| Stage A 420k baseline (pre-reboot) | MAXLEN=430080, probabilistic draft, MAX_BATCHED=8192 | 44.9 | 22.1 | 103.8 | 1520 | 4.82 | baseline |
| B1a | vm.swappiness 60 -> 10 (host) | n/a | n/a | n/a | n/a | n/a | kept as hygiene; decode 73.7 within band, not a measured win |
| **B3 greedy draft** | `draft_sample_method=greedy` | **70.8** | **29.1** | (per 47.2) | 1088-1162 | 4.36 | **ACCEPT** (+30/36/31% C1 vs boot2; C4 +25%) |
| B2 k=10 | SPEC_K=10 | 59.9 | 19.3 | (per 31.2) | n/a | rate 34.3% | REJECT (C4 -34%, decode -13%) |
| B2 k=4 | SPEC_K=4 | 64.9 | 34.6 | (per 46.9) | n/a | 3.87 | REJECT (C1 code -8%, math -10%, decode -6%) |
| B6 fusion | compilation `pass_config` fusion passes | 73.1 | par | (per 35.4) | n/a | n/a | REJECT (C4 -25%, decode -12%) |
| post-reboot champ A | champion (greedy, 8192) | 69.94 | 32.17 | 167.1 | n/a (cache artifact) | 4.44 | drift reference |
| post-reboot champ B | champion (greedy, 8192) | 68.78 | 32.06 | 136.8 | 1114 | 4.38 | drift reference |
| **B7** | **MAX_BATCHED=16384** | ~68.4 (6 reps) | 31.7 | 168.0 | 935 | 4.28 | **ACCEPT** (+8.4%/+12.8% decode in 2 independent runs; gates pass incl 400k NIAH) |
| B9 | NCCL_ALGO/PROTO/BUFFSIZE sweep | n/a | n/a | n/a | n/a | n/a | SKIP — no variant beat baseline (see below) |
| combo A1 | baseline (probabilistic, 8192) | 69.28 | 24.32 | 173.7 | 1118 | 4.34 | A/B/A leg 1 |
| combo B | champion (greedy, 16384) | 64.25 | 27.28 | 125.9 | 601 | 4.29 | A/B/A leg 2 (decode 74.59) |
| combo A2 | baseline (probabilistic, 8192) | 72.71 | 29.14 | 164.9 | 1042 | 4.31 | A/B/A leg 3 (decode 74.06) |
| B10 | DSV41_ENGRAM_DISK_THREADS=64 | 71.38 | 28.96 | (per 38.8) | 1144 | 4.36 | REJECT (neutral) |
| B4 | clock unlock | n/a | n/a | n/a | n/a | n/a | NOT RUN (timebox) |
| B5 | MoE/prefill backend | n/a | n/a | n/a | n/a | n/a | research only, not A/B'd (timebox) |
| B8 | DeepSelect | n/a | n/a | n/a | n/a | n/a | prepared (clone+submodules+build script), build not attempted (memory) |
| **final champion** | greedy + MAX_BATCHED=16384 | **71.44** | **31.70** | **169.1** | **1495** | **4.78** | **SHIPPED** |

`C4 coding agg` = median aggregate tok/s for the C4 coding batch; `prefill@32k` = unique-prefix cold probe (noisy, see caveats).

## Final champion tables (phase4/final-champion/)

Tony prompt set v1 (per-stream / agg tok/s):
- C1 coding 71.44 / 66.03; json 45.26 / 39.23; narrative 27.68 / 26.44; prose 31.70 / 29.88; math 69.95 / 63.25; reasoning 58.57 / 53.72; summary 27.92 / 24.79; format 71.21 / 57.62; ceiling_count 83.22 / 76.77
- C2 coding 64.85 / 117.43; C3 coding 52.77 / 143.11; C4 coding 47.04 / 169.10; C5 coding 41.50 / 190.41; C6 coding 38.61 / 206.83 (agg)
- Cold prefill (unique prefix): 2k 1659, 8k 1477, 32k 1495, 64k 1431, 100k 1416 tok/s
- `bench-decode` (2048-tok, n=10) valid medians: 73.39, 73.99, 74.67, 66.07 -> median 73.7 tok/s
- `bench-depth`: 5k 44.2, 10k 44.3 tok/s; C4 aggregate 136.2 tok/s (per-stream 36.0/38.7/36.5/39.6)
- DSpark accept length: n=175, mean 4.78, median 5.17, rate 75.5%
- Gates on the final world: arithmetic, JSON, tool-call, tool-roundtrip, temp0 determinism, NIAH 32k x3 depths, NIAH 400k (397,753 tok, TTFT 323 s, 1231 tok/s) — ALL PASS (`gates-final-champion.log`)
- gpuflip clean (world down): all 4 nodes all-fast, 60s shared all-fast 60s, slow 0s; clocks 2184-2190 MHz, power 23-26 W. Per-node power under load from telemetry CSVs.

## B9 NCCL pre-screen (world down, vLLM pynccl, 0% slow all runs)

| variant | collective cost/step p50 eager | graph |
|---|---|---|
| baseline | 4.40 ms | 5.17 ms |
| NCCL_ALGO=Tree | 6.82 | 8.68 |
| NCCL_ALGO=Ring | 4.66 | 5.87 |
| NCCL_PROTO=LL128 | 6.24 | 8.03 |
| NCCL_PROTO=Simple | 7.69 | 8.88 |
| NCCL_BUFFSIZE=4M | 4.56 | 5.57 |

No variant improves on baseline; no relaunch warranted.

## Caveats / honesty notes

- **Short-generation C1/C4 metrics are noisy.** C1 coding reps swing 52-74 tok/s within a single boot; C4 coding aggregate swings 120-175 across boots of identical config. Only `bench-decode` (single-stream, 2048 tok) and accept length are reasonably stable, and even bench-decode drifts ~12% across boots of the probabilistic baseline (66.1 vs 74.1). Accept/reject calls lean on bench-decode + gate correctness, not on C1/C4 medians.
- **The A/B/A combo is inconclusive on C1/C4** because the probabilistic baseline's own two legs disagree (decode 66.1 vs 74.1; C1 math 52.5 vs 69.0). On decode, champion B (74.59) ~ baseline A2 (74.06) > baseline A1 (66.12). The clean greedy-vs-probabilistic win was established pre-reboot in B3 (same harness), not re-established here.
- **B7 acceptance rests on a consistent separation** within the greedy family: greedy+8192 gave 65.46/65.47 (2 boots) vs greedy+16384 gave 70.98/73.82/74.59 (3 boots), while probabilistic+8192 gave 66.12/74.06 (inconsistent). The +8.4% decode gain is real for the greedy config but the cross-config drift is large; treat B7 as a modest win, not a large one.
- **prefill-probe@32k is unreliable** when the probe prompt collides with a cached prefix (champ-postreboot 32k/100k read 92k/227k tok/s = cache hits). The `v41bench` in-run prefill sweep (final champion 2k-100k = 1659-1416 tok/s) is the trustworthy prefill series.
- **gpuflip with the world live is invalid** (forge OOM on probe allocation; flame read a false "slow" state from host-memory contention). Only the world-down run is authoritative.
- `lmx-capture.py` needed a `User-Agent` header added for localmaxxing.com (Cloudflare 403 on the default urllib UA); backup at `lmx-capture.py.preb4b.bak`. `LMX_KEY` was not present in the environment, so `--capture` ran for both prompts and `--dry-run`/`--submit` were NOT run.

## Not run (timebox)

- **B4 clock unlock**: would require stopping `spark-gpu-clock-lock` on the shared cluster, benching, then restoring; post-reboot probes showed no slow state with the lock active, so expected value was low and risk non-trivial. Documented, not executed.
- **B5 MoE/prefill backend A/B**: research done — the live MoE backend is `DEEPGEMM_MXFP4` (`DeepGemmFP4Experts`, `MoEPrepareAndFinalizeNoDPEPModular`); MXFP8 GEMM uses `FlashInferCutlassMxfp8LinearKernel`. Candidate switches in `vllm/envs.py`: `VLLM_MOE_USE_DEEP_GEMM`, `VLLM_MOE_SKIP_PADDING`, `VLLM_USE_FUSED_MOE_GROUPED_TOPK`, `VLLM_MAX_TOKENS_PER_EXPERT_FP4_MOE`, `VLLM_B12X_MOE_FP4_FORCE_A16`, and `--moe-backend flashinfer_cutlass|triton|marlin`. None A/B'd.
- **B8 DeepSelect**: cloned `deepseek-ai/DeepSelect` + submodules (cutlass/kerutils) on forge, gencode patch + build script prepared (`phase4/b8-deepselect-build.sh`, adds sm_120/sm_121a, disables the reg-spill gate). Build not attempted: the live world leaves only ~5-9 GiB MemAvailable per node and a cutlass-heavy CUDA build would OOM / disrupt the shared cluster.
- **B10 ENGRAM_THREADS=16**: only 64 was tested (neutral).
- **B7b chunked prefill 4096**: not applicable — `--max-num-batched-tokens` IS the chunked-prefill chunk size in this build; no independent knob.
