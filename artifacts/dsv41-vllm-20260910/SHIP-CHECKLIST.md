# Ship checklist — DeepSeek-V4.1-Flash on 4× DGX Spark (vLLM TP4)

Agreed with Jun 2026-09-10 19:11 PDT. Group D (upstream/community filings) is **deliberately
skipped** — decided, not forgotten.

State when written: world live at 420k, DSpark k=5 + greedy draft (accepted arm), all gates
passing, tuning campaign in its final arms (B8/B9 in flight), DGX-dash updated (maxSeqs 4).

## A. Finish the campaign (measurement)
- [ ] B7 batched-tokens 16k (re-run; the pre-reboot run was invalidated)
- [ ] B4 clock unlock — bench prefill + decode, run gpuflip under load, **restore the lock**
- [ ] B5 MoE / prefill backend check (find the kernel actually in use; A/B plausible env switches)
- [ ] B8 DeepSelect (in flight; 45-min time-box, wire in only if it builds and self-tests pass on GB10)
- [ ] B9 NCCL sweep (in flight; pre-screen with nccl_lat.py, relaunch only for winners)
- [ ] B10 engram reader threads (32 vs 16/64; pinning is an A/B, not a recommendation)
- [ ] Stage C: combo A/B/A at 420k + full tables → `phase4/RESULTS.md`
      (Tony set C1–C6, bench-decode ×5, bench-depth 5k/10k + C4, prefill 8k/32k/100k/400k,
       accept length per category, gpuflip + power per node)
- [ ] Freeze `CHAMPION.env`, relaunch armed
- [ ] **30–60 min sustained soak** on the final champion (only 5-min soaks so far)
- [ ] Full gates on the final champion: arithmetic, JSON, tool round-trip, corrcheck 7/7,
      NIAH 32k / 100k / **400k**, vision

## B. Production readiness
- [ ] **Auto-recovery on node reboot** — a single worker reboot kills the whole TP4 world and
      currently needs manual recovery. Add a systemd unit or a one-command documented recovery,
      then **prove it by rebooting a worker** (after the campaign).
- [ ] **Concurrency contract**: launcher `SEQS=8` vs dash `maxSeqs 4` — pick one, publish the
      per-depth table (C4 = 56% of C1 per-stream, C8 = 27%).
- [ ] Verify `sparks/auto` (and worker model refs) resolve to this world so our agents use it.
- [ ] Rollback chain documented and tested: champion → previous champion → SGLang spec-off lane
      (`launch-dsv41-tp4.sh`) → qwen (`qwen38-tuning-20260906/rollback-serve.sh`).
- [ ] Decide shipped context: 420k (current, 430080) vs 300k — KV pool vs page-cache headroom.

## C. Publishing
- [ ] spark-bench README section "DeepSeek V4.1 Flash — 4× DGX Spark" (honest-map protocol:
      prompt depth + task type + thinking state on every number), dashboard screenshot,
      attribution. Docs index already written: `DOCUMENTATION-INDEX.md`.
- [ ] LocalMaxxing Verified runs: capture `code-v1` + `reasoning-v1` (`lmx-capture.py --capture`),
      `--dry-run`, **Jun approves payloads**, then submit; record receipts.

## D. Upstream / community — SKIPPED by decision (2026-09-10)
Deferred: SGLang DSpark corruption report, SGLang DSML parser issue+PR, comment on tonyd2wild
issue #1 (our all-fast clock-lock result + greedy-draft finding), offer of the parallel row-store
to 0xSero. Consequence to remember: the SGLang lane stays spec-off (correct but ~13 tok/s) and
the DSML parser bug stays unfiled. If either becomes relevant again, the evidence is already
collected in `sglang-lane/` and `STATUS-sglang-phases1-2.md`.

## E. Housekeeping
- [ ] Rotate the LocalMaxxing API key (it was pasted into chat; the harness reads it from env only).
- [ ] Record `vm.swappiness=10` on all 4 nodes and the clock-lock state as part of the shipped config.
- [ ] Final backup sweep: all artifacts under `artifacts/dsv41-vllm-20260910/` pushed; nothing
      important living only on forge.
