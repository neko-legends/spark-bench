# Phase 3 handoff: DeepSeek-V4.1-Flash on 4×GB10 with vLLM — Tony's recipe + everything we already know

Owner: Depths. Report channel: dm-depths. Timebox 8h. STATUS file: `/home/jun/nest/tmp/dsv41-port-20260910/STATUS.md` → add `## Phase 3 (vLLM)`; update at every stage boundary and every failed boot. If time runs out, leave it accurate and stop.

## 0. Decision and goal (Jun, 2026-09-10 09:25)
"We don't have to copy him exactly, we can use best of everything we know, and use vLLM." Engine = **vLLM** (Tony's `dsv41-feat` lineage). The SGLang lane (image `local/dsv41-gb10:p2`, launcher `/home/jun/launch-dsv41-tp4.sh`) stays as a correct fallback; do not delete it. Goal: a vLLM TP4 world with **working DSpark**, passing our gates, benched two ways (comparable to Tony AND to our V4 Flash numbers), left running.

## 1. Sources
- **Tony's repo (primary recipe):** https://github.com/tonyd2wild/DeepSeek-V4.1-Flash-vLLM-DGX-Spark — clone on forge to `/home/jun/dsv41-vllm/tony` (pin the commit; as of 12:23 ET it's `ca662ac`, boot 10). Read fully: `README.md`, `docs/RECIPE.md`, `docs/*.md` (one post-mortem per failure — read them BEFORE building; they are the failure modes you will hit), `patch/README.md` + `patch/mounts.txt` (the 7 bind-mounted files with md5s), `build/*`, `launch/boot10-go.sh`, `launch/dsv41-tp4.sh`, `launch/boot_dsv41.sh`, `tools/gpuflip.py`, `tools/flipsum.py`, `tools/nccl_lat.py`, `bench/prompts-v1.json`, `tools/bench_report.py`.
- **Our V4 Flash recipe (our own prior art, same fabric, same engine family):** `/home/jun/git/spark-bench/README.md` §"DeepSeek V4 Flash", `scripts/start-dspark-tp4.sh`, `scripts/status-dspark-tp4.sh` ("OK: speculative decoding live" gate; disarmed boot → arm auto-restart only after API + spec gate), `scripts/bench-decode.py`, `scripts/bench-depth.py`, `docs/FABRIC.md`, `results/sglang-vs-vllm-2026-08-20.md` (NCCL_IB_GID_INDEX=auto lesson). Existing V4 launcher on forge: `~/dspark-2x-0731-abliterated-nvfp4/start-dspark-tp4.sh` and the anemll `dspark-vllm-gx10` image lineage — read for NCCL/ConnectX env.
- **Our phase-1/2 artifacts:** `/home/jun/nest/tmp/worker-handoffs/depths-dsv41-nvme-port-20260910.REPORT.md`, `/home/jun/dsv41-port/` (gates: corrcheck, NIAH, tool round-trip repro under `p2/repro/`).
- **Qwen campaign harness:** `/home/jun/git/spark-bench/models/qwen-3.8-flash-next/benchmarks/{q38bench.py,corrcheck.py,niah2.py,tel-collect.sh,soak.py}`.

## 2. What we already have that improves on Tony's setup (use it)
- **Full checkpoint local on all 4 nodes** (`/home/jun/models/deepseek-v4.1-flash`, sha256-verified). Tony serves workers over NFS and needed a separate `engram_local.py` copy step. We need neither: every rank reads weights AND engram rows from local NVMe. Verify `patch/engram.py`'s path logic works with a plain local model dir on every rank (it should — the head in his setup does exactly this). No NFS anywhere.
- **GPU clock lock** `spark-gpu-clock-lock.service` (2200 MHz) active on all 4 nodes. Keep it.
- **Fabric**: 192.168.10.0/24 RoCE via MikroTik CRS812, IFACE `enP2p1s0f1np1`, HCA `roceP2p1s0f1`, NCCL_NET=IB, ROCEv2, `NCCL_IB_GID_INDEX=auto`, MTU 9000 — copy from `/home/jun/launch-dsv41-tp4.sh` / `/home/jun/launch-qwen38-tp4.sh`. Tony's IPs are 192.168.192.x — translate.
- **Serving hardening**: disarmed boot → API up → spec-decode-live gate → arm restart. Port the pattern.
- **Gates + bench discipline**: fail-closed benches, ≥3 reps, medians, boot-to-boot drift check; quote prompt depth/task/thinking state with every number.
- **Two DSML-parser findings** from phase 1: this model emits tool parameters WITHOUT `string="..."` at temp 0 (deterministic). SGLang's parser dropped them silently. Check vLLM's `deepseek_v41` tool parser on the same repro (`/home/jun/dsv41-port/p2/repro/` has the exact second-turn prompt); if it drops params too, patch (bind-mount) and note — that would be a second upstream bug report.

## 3. Stages

### S1 — Prep (≤30 min)
1. Confirm the SGLang perf worker is stopped and the SGLang containers are down on all 4 nodes (`docker ps | grep dsv41`). If a `dsv41-rank*` container is still up, **stop it** (`docker stop dsv41-rank0..3` via the hosts) — the vLLM kernel prebuild needs the host memory (Tony's boot-3 wedge: runtime JIT with 22 jobs exhausted host RAM on all four nodes and the watchdogs reset them). Never run two worlds.
2. Clone Tony's repo on forge; record commit. `rsync` the repo to .2/.3/.4 too (builds are node-local).
3. **GPU slow-state probe** (Tony issue #1): run `tools/gpuflip.py` (and `flipsum.py`) on each node while idle; record per-node fast/slow classification and power draw in STATUS. This is a real data point for his issue; save outputs to `/home/jun/dsv41-vllm/gpuflip/<node>.txt`.

### S2 — Image chain, all 4 nodes (target ≤3h; run nodes in parallel, watch `free -g`)
Follow `docs/RECIPE.md` §3 exactly: overlay1 (pinned vLLM nightly merge-base + `_C_stable_libtorch` sm121 ext via `build/Dockerfile.overlay` / `build_stable_ext.sh`) → overlay3 (FlashInfer v0.7.0rc1 `07869c61`, remove stale 0.6.18 caches) → overlay4 (prebuild `mxfp8_gemm_cutlass_sm120`, `MAX_JOBS=2`) → overlay5 (`build_overlay5.sh` + `prewarm5.py`; then `verify5.py` must confirm nothing compiles at runtime). Tag final as `local/vllm-dsv41:overlay5`. If any overlay's base image isn't pullable, stop and report — don't improvise a different vLLM commit.
Record per-node image IDs; they must match (or explain why not — node-local builds can differ in JIT artifacts; `verify5.py` is the real gate).

### S3 — Patches + launcher (≤45 min)
- Copy the 7 files from `patch/` per `patch/mounts.txt` to `~/patches/dsv41-boot10/` on every node; verify md5s against `patch/README.md`.
- Write `/home/jun/launch-dsv41-vllm-tp4.sh` (forge) by adapting `launch/dsv41-tp4.sh` + `launch/boot10-go.sh` + `launch/boot_dsv41.sh`: our IPs/IFACE/HCA/NCCL env, model path local on every rank (no NFS, `ENGRAM_LOCAL` not needed — confirm), rank order workers 3,2,1 then head 0, `--block-size 128`, DSpark k=5, `FULL_AND_PIECEWISE` CUDA graphs with exact capture sizes (his `dsv41-tp4-graphs.diff` / `patch_launcher.py`), gmu 0.80, `--max-model-len` start at 131072 (raise to 300k after gates), tools + vision on (`deepseek_v41` parsers). Port our disarmed-boot pattern: no restart policy until the spec gate passes. Include Tony's "stop every node first, head first" relaunch rule (his fix #6 — a new worker joined a stale head's rendezvous).
- Pre-launch: `tools/nccl_lat.py` 4-node all-reduce check; gpuflip on all 4 again.

### S4 — Boot & gates (≤90 min, iterate)
- Boot; expect per-rank ~81 GiB weights with DSpark draft layers. Tail all 4 logs; look for `Engram DISK mode: layer L rows [start, end)` on every rank (rank-offset fix present → ranges differ per rank).
- Spec gate: adapt `scripts/status-dspark-tp4.sh` → must show speculative decoding live (vLLM SpecDecoding metrics / acceptance in logs).
- Correctness: arithmetic 42; JSON schema; **tool round-trip with the phase-1 repro** (this is where SGLang+DSpark corrupted — if vLLM+DSpark is clean here, that's the headline finding); corrcheck 7/7; NIAH 32k + 100k; one image; 5-min C4 soak (RSS flat, no swap).
- If DSpark corrupts here too → that changes the diagnosis (model/tokenizer-boundary, not engine); record precisely and fall back to spec-off for the remaining gates.

### S5 — Bench two ways (≤60 min)
1. **Tony-comparable:** `bench/prompts-v1.json`, C1–C6, temp 0, thinking off, warmup first, `usage`-block token counts, his `tools/bench_report.py`. Compare to his boot-10 table (C1 code 73.8, mean 43; C6 agg 132).
2. **V4-Flash-comparable (ours):** `bench-decode.py` (C1 record protocol) + `bench-depth.py` (5k/10k + C4), so V4.1 sits next to V4 Flash's 136 / 66–93 / 182 in spark-bench.
3. Telemetry alongside every run: `tel-collect.sh` **plus power draw** (`nvidia-smi --query-gpu=power.draw,clocks.sm`), and a gpuflip snapshot before/after — Tony's slow state moves cells 1.5×; we must know which state we measured in.
4. Record DSpark acceptance length per category.

### S6 — Leave it running + report
Final state: vLLM world serving on :8000 (head 192.168.10.1) if gates pass; otherwise SGLang p2 relaunched (spec-off) via `/home/jun/launch-dsv41-tp4.sh` so the cluster is never left empty. REPORT.md: exact working launch, per-rank memory, gate results, both bench tables, gpuflip states, patches used (with md5s), deviations from Tony's recipe and why, rollback notes (SGLang lane + qwen `rollback-serve.sh`).

## 4. Constraints
No changes under `/home/jun/models/`; keep `local/qwen38-gb10:*` and `local/dsv41-gb10:*` images; don't touch the eva-core host service; no GitHub pushes; all inference local; one TP4 world at a time; every change reproducible (scripts/Dockerfiles/patch dirs in `/home/jun/dsv41-vllm/`). Attribution: Tony (recipe, patches, slow-state finding), Kai (SM12x patches, first engram-on-disk), vLLM team (`dsv41-feat`), DeepSeek (model) — carry into REPORT.md.

## Addendum 09:52 PDT (state at spawn)
- SGLang perf worker STOPPED by Depths; all `dsv41-rank*` containers stopped on all 4 nodes; ~117 GB free per node. S1.1 is already done — verify and move on.
- Final SGLang DSpark matrix (all corrupt, byte-identical or same family): stock, `--disable-cuda-graph-padding`, `--speculative-dspark-align-verify-tokens-to-graph-tier`, block-size 4, SWA bounded-replay off (`</tool_result>` runaway variant). Eager inconclusive. Artifacts: `forge:/home/jun/dsv41-port/p2/repro/`. Do NOT continue SGLang work; that lane is closed for this handoff.
- Relevant upstream context to carry into the report: SGLang PR #38879 (DSpark verify rewrite, merged 2026-09-10 13:58 UTC, after our SGLang image); PR #33872 (closed; compress-ring under-write under spec verify — same symptom family). Not your job to chase — just cite.
