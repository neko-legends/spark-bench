# Phase 4b handoff: resume the DSV4.1 vLLM tuning campaign after the anvil reboot

Owner: Depths. Channel: dm-depths. Timebox 6h. STATUS: append `## Phase 4b (resume)` to `forge:/home/jun/dsv41-vllm/STATUS.md`.

## What happened (read first)
The phase-4 campaign was interrupted at ~17:50 PDT when the head node lost rank 1 (anvil) to a manual reboot. The world hung; the previous worker's launcher stalled; Depths cleared the stuck launcher + all four containers (head-first) and relaunched the champion config manually:
`DRAFT_METHOD=greedy MAXLEN=430080 GMU=0.80 SEQS=8 SPEC_K=5 ENGRAM_THREADS=32 MAX_BATCHED=8192 bash /home/jun/launch-dsv41-vllm-tp4.sh` (log: `logs/boot420k-recover.log`).
Arm **B7 (MAX_BATCHED=16384) is INVALID** — it booted into the reboot and was never measured. Re-run it as the first arm.

## START GATE
Wait until `curl -s http://192.168.10.1:8000/health` returns OK AND `/v1/models` lists `deepseek-v4.1-flash`. If not healthy within 30 min of spawn, inspect `logs/boot420k-recover.log`; if the launcher died, relaunch with the champion env above.

## Resume state (authoritative)
- Champion (`forge:/home/jun/dsv41-vllm/CHAMPION.env`): MAXLEN=430080, GMU=0.80, SEQS=8, SPEC_K=5, DRAFT_METHOD=**greedy**, ENGRAM_THREADS=32, MAX_BATCHED=8192; host-level `vm.swappiness=10` on all 4 nodes (keep).
- Accepted so far: **B3 greedy draft** (C1 coding 54.5→70.8, math→72.9, prose→29.1; C4 coding +25%; gates PASS).
- Rejected/closed: B2 k-sweep (k=5 optimal; k=4 rejected −8/−10%; k=10 rejected; k must be divisible by draft n_predict=5 so k=6/7 impossible), B6 compile-fusion passes (C4 −25%, bench-decode −12%), B1a swappiness (kept as hygiene, not a measured win).
- Sequence cap already applied to DGX-dash: maxSeqs 4, context 430080 (verified via runtime-capacity API).
- Method is in the phase-4 handoff `/home/jun/nest/tmp/worker-handoffs/depths-dsv41-tune-20260910.md` (read it fully): one variable at a time, ≥3 reps, report per-rep values, accept only >3% beyond boot-to-boot drift **with gates passing** (arithmetic, JSON, tool round-trip, corrcheck 7/7, NIAH), champion updated after every acceptance, `CHAMPION.env` refreshed, backup to `/home/jun/git/spark-bench/artifacts/dsv41-vllm-20260910/phase4/` + commit/push (Depths identity, `Agent: depths` trailer) after every acceptance.

## Mandatory post-reboot checks (do before judging any arm)
1. `spark-gpu-clock-lock` active on all 4 nodes; `nvidia-smi --query-gpu=clocks.sm,power.draw --format=csv,noheader` under load should read ~2.19 GHz.
2. Run `/home/jun/dsv41-vllm/tony/tools/gpuflip.py` + `flipsum.py` on all 4 nodes (anvil just rebooted — this is a clean-state test for Tony's slow-state issue). Save to `phase4/gpuflip-postreboot/`. All-fast is the expected result; slow state on any node is a finding to report, not to work around.
3. Re-establish the drift band if the numbers look shifted vs the pre-reboot champion (one extra champion relaunch + bench).

## Remaining arms (in order)
1. **B7 re-run**: MAX_BATCHED=16384 (+ chunked prefill 4096 as a separate arm B7b only if B7 is accepted or neutral).
2. **B4 clock unlock**: stop `spark-gpu-clock-lock` + `nvidia-smi -rgc` on all nodes, bench (decode + prefill at 8k/32k), run gpuflip during load, then RESTORE the lock and re-verify. Measures the 2200 MHz cap cost on prefill (compute-bound) vs decode (bandwidth-bound).
3. **B5 MoE/prefill backend**: grep the head log for the MoE kernel/backend actually in use; list MOE/MXFP4/FLASHINFER env switches from `/home/jun/dsv41-vllm/vllm-src/vllm/envs.py`; A/B the plausible ones one at a time. Metric: cold prefill 8k/32k + TTFT; decode must not regress.
4. **B8 DeepSelect** (time-box 45 min): clone `deepseek-ai/DeepSelect`, add a `compute_120`/`121a` gencode, build inside `local/vllm-dsv41:overlay5`. If it builds and self-tests pass on GB10, wire it in as the indexer top-k A/B; else note and move on.
5. **B9 NCCL sweep**: pre-screen with `tony/tools/nccl_lat.py` (5 min per variant) for `NCCL_ALGO=Tree|Ring`, `NCCL_PROTO=Simple|LL|LL128`, `NCCL_BUFFSIZE`; relaunch only for the 1–2 variants that improve latency.
6. **B10 engram reader threads**: `DSV41_ENGRAM_DISK_THREADS` 16 / 64 vs 32; optionally CPU pinning of the reader threads (our qwen affinity test was −3%, so treat as an A/B, not a recommendation).

## Stage C — combo + final (required)
- Combo verification A/B/A at 420k: champion vs original baseline (greedy off, probabilistic draft), 3 reps each, full reports.
- Final tables: Tony prompt set v1 C1–C6, `bench-decode.py` ×5, `bench-depth.py` (5k/10k + C4), cold prefill 8k/32k/100k/400k, accept length per category, gpuflip + power per node.
- Leave the champion running, armed, and write `## Final` in STATUS with the exact launch command.
- **LocalMaxxing submission**: run `forge:/home/jun/dsv41-vllm/lmx-capture.py` (written by Depths; read it first) for `code-v1` and `reasoning-v1`: `LMX_KEY=<key> python3 lmx-capture.py --capture --prompt code-v1 --max-tokens 600` then `--dry-run`. **Do NOT submit** (`--submit` requires `LMX_CONFIRM=yes`) — Depths submits after Jun approves the payloads. The key is provided at runtime only: never write it to a file, artifact, log, or commit. If the key is unavailable, stop at `--capture` and note it.
- Backup everything to spark-bench `phase4/` + `RESULTS.md` (arm | knob | median C1 code | C1 prose | C4 agg | prefill@32k | accept len | verdict + why), commit/push, and write REPORT.md.

## Constraints (unchanged)
One TP4 world at a time; never leave the cluster without a working world; do not modify `/home/jun/models/`; keep all images; don't touch the eva-core service; push only to `/home/jun/git/spark-bench` and `/home/jun/git/DGX-dash`; all inference local; restore host-level changes (clock lock) except those documented as part of the champion. Attribution: tonyd2wild + Kai, 0xSero, LMSYS, vLLM team, DeepSeek.
