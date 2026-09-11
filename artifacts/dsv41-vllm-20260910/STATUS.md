# DSV41 vLLM Phase 3 STATUS

## Stage
S1 prep (started)

## Started
2026-09-10 (phase-3 worker spawn)

## Log
- S1.1 verified: no dsv41-rank* containers running on any node; ~116-117 GB free/node.
- Tony repo cloned on forge: /home/jun/dsv41-vllm/tony @ ca662ac35193c69ace9cee37f13a94abf2eff0fc (boot 10).
- Base images verified to exist on Docker Hub: nightly-8a728663... and deepseekv41-flash-0909-arm64.
- vllm dsv41-feat branch exists upstream (head e47aa780).

## Phase 3 (vLLM) — S1 prep
- 2026-09-10: SGLang containers down on all nodes (verified, ~117 GB free). Repo rsynced to anvil/ember/flame. vllm dsv41-feat source cloned on forge (e47aa780) → /home/jun/dsv41-vllm/vllm-src.
- GPU slow-state probe (idle, all 4 concurrently, 80s): ALL FAST, zero flips. gemv_cont p50 217-219 GB/s, mm_duty 81-84 TFLOPS, clocks 2171-2190 MHz under load, 18-25 W. Outputs: /home/jun/dsv41-vllm/gpuflip/flip-<node>.txt + flipsum: shared 60s all-fast 60s / slow 0s. (Tony issue #1 data point: no slow state observed on this fleet with clock lock active.)
- Base image pull of vllm/vllm-openai:nightly-8a728663... started on all 4 nodes.

## S2 image chain (COMPLETE, ~25 min, no wedge)
- overlay1 built per node: base vllm/vllm-openai:nightly-8a728663c1c3... + dsv41-feat python tree (e47aa780) + _C_stable_libtorch rebuilt sm_121a (82/82 steps, 29MB .so). overlay1 forge fad2073af1e6.
- overlay3 (FlashInfer 0.7.0rc1 07869c61 pinned submodules), overlay4 (mxfp8_gemm_cutlass_sm120 prebuilt, MAX_JOBS=4, minAvail ~90GiB — no boot-3 wedge), overlay5 (sparse_mla rebuilt under runtime env). Final tagged local/vllm-dsv41:overlay5 + vllm-dsv41:overlay5.
- Image IDs differ per node (node-local builds, expected): forge 1efef58714e9, anvil 61d5b829c1b2, ember ffaf91bab36e, flame 2fcf9e4c0260. All 23.3GB.
- Runtime no-JIT check on each node: mxfp8 build_and_load 1.4s (ninja no-op), sparse_mla 0.0s. NOTE: verify5.py prints "MISS" for mxfp8 — try_load() in flashinfer 0.7.0rc1 always returns None for JIT specs; the real gate (no compile at runtime) passes, matching Tonys doc 1.5s, no compile.

## S2 image chain (COMPLETE, ~25 min, no wedge)
- overlay1 built per node: base vllm/vllm-openai:nightly-8a728663c1c3... + dsv41-feat python tree (e47aa780) + _C_stable_libtorch rebuilt sm_121a (82/82 steps, 29MB .so). overlay1 forge fad2073af1e6.
- overlay3 (FlashInfer 0.7.0rc1 07869c61 pinned submodules), overlay4 (mxfp8_gemm_cutlass_sm120 prebuilt, MAX_JOBS=4, minAvail ~90GiB - no boot-3 wedge), overlay5 (sparse_mla rebuilt under runtime env). Final tagged local/vllm-dsv41:overlay5 + vllm-dsv41:overlay5.
- Image IDs differ per node (node-local builds, expected): forge 1efef58714e9, anvil 61d5b829c1b2, ember ffaf91bab36e, flame 2fcf9e4c0260. All 23.3GB.
- Runtime no-JIT check on each node: mxfp8 build_and_load 1.4s (ninja no-op), sparse_mla 0.0s. NOTE: verify5.py prints "MISS" for mxfp8 - try_load() in flashinfer 0.7.0rc1 always returns None for JIT specs; the real gate (no compile at runtime) passes, matching Tony's doc "1.5s, no compile".

## S3 patches + launcher + pre-launch (COMPLETE)
- Patches staged ~/patches/dsv41-boot10/ on all 4 nodes, 8 files, md5-verified identical to Tony patch/README.md (c0329107/0a14bee6/7e1027f1/da9ef196/af0f8447/cc419353/a9b73756/79a774bc).
- Launcher: forge:/home/jun/launch-dsv41-vllm-tp4.sh — Tony boot10 config translated to our fabric (rail B, GID auto, local model on every rank, no NFS/no ENGRAM_LOCAL), stop-all-head-first, disarmed boot -> API -> spec gate -> arm unless-stopped. Image-ID check relaxed to warn (node-local builds differ).
- NCCL 4-node collective check (nccl_lat.py, pynccl, our env): all ranks lockstep, 60KB p50 66us, collective cost/step 4.4-5.7 ms, 0% slow steps. Outputs: /home/jun/dsv41-vllm/nccl/.
- gpuflip pre-launch: all 4 fast again, zero slow seconds. /home/jun/dsv41-vllm/gpuflip/flip-*-preboot.txt.

## S4 boot + gates (COMPLETE — ALL GATES PASS, DSpark ON)
- Two launcher bugs fixed en route: JSON args ({image:4}, speculative-config) lost quotes when baked into the per-rank script via heredoc -> defined at runtime in generated script now; added head-container-death early exit. Logs: /home/jun/dsv41-vllm/logs/boot1b-launch.log.
- Boot: workers 3,2,1 then head 0; load 48 shards 40s/rank + DSpark draft second pass; autotune ~4 min; API up ~15 min. Spec gate PASS (39 spec metrics, SpecDecoding log lines), armed unless-stopped.
- Engram DISK mode per rank: contiguous distinct ranges layer1 [0/96M/192M/288M, ...] — rank-offset fix confirmed on all 4 ranks.
- GATES (all on DSpark k=5 + CUDA graphs, MAXLEN=131072):
  1. Arithmetic 19+23: PASS (content "42", finish stop, reasoning_tokens 0)
  2. JSON schema: PASS ({'answer': 42})
  3. **Tool round-trip (phase-1 SGLang corruption repro): PASS CLEAN — lookup_fixture {'key':'alpha'} parsed (vLLM deepseek_v41 parser does NOT drop string=-less params), continuation "The value for key **alpha** is **42**.", finish stop. No </tool_result> runaway. HEADLINE: DSpark corruption was SGLang-side, not model-bound.**
  4. corrcheck 7/7 PASS
  5. NIAH 32k 6/6 + 100k 6/6 PASS
  6. Vision: PASS on content ("A red circle on the left and a blue square on the right."); NOTE image_tokens field not exposed by vLLM usage (prompt_tokens 905 = ~891 img + 14 text)
  7. 5-min C4 soak: PASS (122 reqs, 0 fail, 304s; worker used-mem deltas <= ~150MB flat; forge swap 938MB steady)

## S5 benches (COMPLETE, all on 131k boot, DSpark k=5, clocks locked 2177-2190MHz, no slow state)
- Tony-comparable (v41bench.py, prompts-v1, temp 0, thinking off, usage-block tokens, warmup first):
  C1 agg 42.96 / per-stream 48.24 (Tony boot10: 37.95/43.12); C6 agg 132.01 (Tony: 131.86); C1 code 70.59 (Tony 73.8);
  prefill cold 2k/8k/32k/64k = 1079/811/1524/1448 tok/s (Tony 902/1026/1539/1194). Files: /home/jun/dsv41-vllm/bench/bench-phase3-131k.{json,md}
- V4-Flash-comparable: bench-decode.py C1 record protocol (2048 tok): median 62.88 tok/s client wall (n=10, sd 10.07, min 47.6 max 74.8; V4 Flash record: 136 median).
  bench-depth.py: 5k median 41.8, 10k median 42.6 tok/s; C4 aggregate 136.7 tok/s (4 streams). Log: bench-depth-131k.log.
- DSpark acceptance: v41bench window mean 4.12 tok/step (156 windows); C1 record protocol window p50 5.24 (min 3.10 max 5.73).
- Telemetry: anvil/ember/flame CSVs (2s samples): clocks pinned 2177-2190 MHz p10-p90, power p50 ~10W idle / max 36-42W decode. forge sampler lost to a redirect bug (script wrote to /dev/null); fixed (tel-sample2.sh) and restarted. GPU slow state: NOT observed at any point (idle flips x2 + locked clocks + no dips).
- Per-rank weights with DSpark draft: 81.58 GiB (matches Tony boot10). CUDA graphs captured (PIECEWISE 15).

## S6 final state (COMPLETE — LEFT RUNNING)
- Relaunched at MAXLEN=300000 (Tony serving config): API up ~19:46Z, KV pool 1,374,757 tokens (4.58x at 300k; Tony 1,070,168/3.57x), weights 81.58 GiB/rank with DSpark draft, CUDA graphs captured. Spec gate PASS, all 4 ranks armed unless-stopped.
- Re-gates on 300k boot: arithmetic 42 PASS; tool round-trip PASS clean; corrcheck 7/7 PASS; NIAH ok:true; count-to-100 after idle 80.3 tok/s, back-to-back 83.6 (correct 1..100 both).
- Boot-to-boot drift (C1 v41bench): 131k boot agg 42.96/48.24 vs 300k boot 43.04/48.71 — within 1%. File: bench/bench-phase3-300k-c1.{json,md}
- Node memory with world serving: ~5-6 GiB MemAvailable per node (same shape as Tony boot10 and our SGLang p2 under load); docker --memory 112g not hit; swap: forge ~0.9GB (pre-existing), workers ~0.2GB.
- Launcher default MAXLEN now 300000 (serving config). Final world: vllm_dsv41 x4 (forge/anvil/ember/flame), http://192.168.10.1:8000/v1, deepseek-v4.1-flash.
- Telemetry samplers stopped (CSVs kept in /home/jun/dsv41-vllm/bench/).

## FINAL
Phase 3 COMPLETE (REPORT.md written). World serving: vllm_dsv41 x4, http://192.168.10.1:8000/v1, deepseek-v4.1-flash, 300k context, DSpark k=5 live. All gates PASS with spec ON.

## Phase 4 (tuning) — started 2026-09-10 13:20 PDT
- Campaign: one-variable-at-a-time arms vs champion, ≥3 reps of short bench, accept = median gain > 3% beyond boot-to-boot drift AND gates pass. Backup after every acceptance to spark-bench artifacts/dsv41-vllm-20260910/phase4/.
- Stage A: relaunch MAXLEN=430080 (420k shipping context, GMU 0.80) — log logs/boot420k-launch.log. 420k baseline = initial champion.
- Arm gate script: /home/jun/dsv41-vllm/phase4/gates.py (arithmetic, JSON, tool call, tool round-trip repro, temp0 determinism, NIAH set). Sanity: PASS on the 300k world before relaunch.

## Stage A (420k) — COMPLETE 2026-09-10 ~15:30 PDT
- 420k boot (MAXLEN=430080): KV pool 1,530,285 tokens, 3.56x concurrency at 430k, weights 81.58 GiB/rank. Boot-to-API ~10 min (warm caches).
- ALL GATES PASS at 420k incl FIRST 400k NIAH: prompt 397,753 tok, needle depth 0.5, TTFT 322 s (1235 tok/s prefill), answer correct. 32k/100k 3/3 depths each pass. Arithmetic/JSON/tool-roundtrip/temp0 pass (phase4/gates-420k-baseline.log).
- 420k baseline bench (phase4/420k-baseline/): C1 agg 29.3 / per 32.8 (coding 44.9, math 44.2, prose 22.1); C4 agg 103.8; C6 agg 139.0 / per 27.1. Cold prefill 2k/8k/32k/64k/100k = 1494/1521/1520/1447/1186 tok/s. bench-decode x3 medians 73.5/70.5/70.7 (trials 63-76, NO 48-tok/s mode on either 420k boot — bimodality not reproduced at 420k). bench-depth: 5k 46.7 / 10k 43.5 / C4 agg 160.5. Accept len mean 4.82 (n=179), rate 76.4%.
- Boot-to-boot drift (drift-boot2): C1 coding median 54.5 (reps 67.0/49.4/54.5 — huge short-batch variance), bench-decode median 67.7 (59.5-74.4), prefill probe 8k/32k second pass 1233/1518 (first probe after load 950/1094 — probe warm-up artifact; use repeated probes). DRIFT BAND: bench-decode ~8% inter-boot; C1 short batches up to ~20% — acceptance variance dominates short generations. Primary arm metric = bench-decode median + prefill probe + accept length.
- NOTE: 131k-boot v41bench numbers (C1 coding 70.6) not reproduced on either 420k boot (44.9 boot1, 54.5 boot2 median). Prefill is FASTER at 420k (1521 vs 811 @8k); long-decode is FASTER (70-75 vs 47-75 bimodal). Only short-batch C1 regressed vs 131k boot — attributed to DSpark acceptance variance (accept 4.12 window mean at 131k vs 4.4-4.8 at 420k), under investigation in B3.
- Sequence cap study (phase4/capstudy.json): 2k-depth per-stream C4 56% of C1, C6 43%, C8 27%. 100k-depth: C2 42% during concurrent prefill (TTFT 115 s), C4 4% (TTFT 187 s). KV pool 1.53M tok (peak 26.6% during 4x100k). RECOMMEND max_num_seqs = 4 (per-stream >=50% of C1 through C4; concurrent 100k prefills serialize TTFT — dashboard should queue long prompts at 2).
- B1a host hardening: vm.swappiness 60 -> 10 on all 4 nodes (persistent until reboot; KEEP per handoff). Post-sysctl bench-decode median 73.7 (sd 1.01) — within drift band, kept as hygiene not a measured win.
- Launcher: added env knobs DRAFT_METHOD / ENGRAM_THREADS / EXTRA_ENV_ARGS / CPUS (defaults = phase-3 behavior, byte-identical commands). Backup: launch-dsv41-vllm-tp4.sh.phase3.bak.

## Arms (vs champion, each: relaunch + gates + 3-rep short bench)
- B3 DRAFT_METHOD=greedy (ACCEPTED, champion 15:27-16:05): C1 coding 70.8 / math 72.9 / prose 29.1 (vs champion 54.5/53.8/22.2 boot2 and 44.9 boot1) = +30/+36/+31%; C4 coding 47.2 (+25%), prose 16.8 (+19%), math 39.0 (-6%); bench-decode median 72.4 min 67.4 (no slow mode); accept len mean 4.36 (unchanged metric); prefill 8k/32k/100k = 1162/1088/1040 (within noisy band, draft unused in prefill). Gates all PASS incl NIAH 32k x3 depths + tool roundtrip. Champion now: greedy draft @ 420k. Phase4 dir: phase4/b3-greedy/.
- B2 SPEC_K=10 (REJECTED 17:20-17:55): valid K values constrained by this build — num_speculative_tokens must be divisible by draft n_predict=5, so K=6/7 impossible, K=4/K=10 tested. K10: C1 coding 59.9 / math 52.9 / prose 19.3 (vs champion 70.8/72.9/29.1); C4 coding 31.2 (-34%); bench-decode 62.1; accept rate 34.3% (vs 67% at K5). Deeper speculation does not pay: per-position acceptance decays, step cost grows. K5 stays.
- B2 SPEC_K=4 (running). DGX-dash live group + forge per-spark maxSeqs updated to 4, context 430080; runtime-capacity API verified (forge:8000 ready, maxSequences 4, deepseek-v4.1-flash).
- Skipped arms with reasons (to date): B9 NCCL sweep — nccl_lat.py needs idle GPUs (world down); phase-3 measured 4-node collectives already optimal (60KB p50 66us, 0% slow steps, 4.4-5.7ms/step), expected effect < noise band. B4 clock-lock-off — phase-3 observed NO slow state on this fleet across two idle probes + all bench telemetry (clocks pinned 2177-2190MHz); uncontrolled experiment risk. B1b GMU 0.78 — GMU bounds GPU memory not host page cache; bimodality (48-tok/s mode) did not reproduce on either 420k boot; KV pool already generous (1.53M).
- B2 SPEC_K=4 (REJECTED 18:25-19:15): C1 coding 64.9 (-8%) / math 65.8 (-10%) / prose 34.6 (+19%); C4 coding 46.9 (par); bench-decode 68.2 (-6%); accept len 3.87 (vs 4.36). Primary metrics regress; K5 confirmed optimal. NOTE: K4 boot re-autotuned 133 fresh FlashInfer configs (new graph shapes) — tuned before serving, not a confound.
- B6 compilation pass_config fusion (REJECTED ~18:00): pass_config {fuse_attn_quant, enable_qk_norm_rope_fusion, fuse_qk_norm_rope_kvcache, fuse_rope_kvcache_cat_mla, fuse_allreduce_rms}=true (the fine-grained equivalents of the handoff enable_fusion/enable_noop — those exact keys do not exist in this vLLM build). C1 coding 73.1 (+3%, within drift) but C4 coding 35.4 (-25%) and bench-decode 63.8 (-12%); C1 math/prose par. Fusion passes regress the parallel decode path. Champion stays without pass_config.
