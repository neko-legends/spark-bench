status: success

# Astra investigation — GLM 5.3 Flash EXL3 TP4

**Investigation complete; no performance improvement claimed. Return to Depths for review, implementation and controlled measurement.**

## Summary / recommendation

The strongest first **optimization experiment** is a narrowly scoped **DFlash2 distributed top-16 candidate reduction**, not removal of the serving-hardening patches. The installed drafter computes/gathers full-vocabulary logits across TP, only to discard all but 16 candidates. A public upstream implementation exists, but cannot be copied verbatim without changing this image's logit semantics. An adapted, unapplied candidate is provided below.

Before that experiment, obtain repeated warmed baselines and verify the actual runtime topology numerically during the approved test window. No new timing, acceptance, memory-usage or throughput measurement was made here.

Main findings:

1. **Pure C1/C4 verification does not accidentally hit EXL3's fat-prefill branch.** Expected k=7 verification shapes are 8/16/24/32 rows, versus EXL3's 128-row cap. Default graph capacity is derived as 64, not 8. SM120 sparse MLA has a separate 64-row decode cutoff. Small mixed-prefill/transition batches are a different case.
2. **Several historical “patch removals” are not removals.** E2 bakes in drafter-group and decode-floor. `SKIP_PATCHES` only skips reapplication; skipping decode-floor also skips the local `SMALL_OK` helper upgrade. The sweep cannot establish collective patch causality, even apart from single-run/cold-boot confounding.
3. **Requested draft TP=1 is not implemented by the inspected V2 DFlash loader.** Its `replace(vllm_config, ...)` retains target parallel configuration; Qwen draft layers read the global TP group. Source predicts a TP4 drafter, not a head-only TP1 drafter. Do not change this to true TP1 as a quick fix: weight sharing, KV geometry and collectives must change together.
4. **`LONG_PREFILL_TOKEN_THRESHOLD=1792` is not forwarded into Docker.** The live PID 1 command omits the flag; installed default is 0. The documented ~1.8k chunk protection must not be assumed present in current measurements.
5. **The live EXL3 binary is still the static round-robin expert scheduler.** A six-file, byte-matched ticket-scheduler backport is available, with no Python adapter change needed. This is a second candidate, not evidence of the historical regression's cause.

## Scope, provenance and constraints

- Public source-of-truth checkout remained **`4bc912877d9f0adfde29e0d4a993378a3ee9974b`**. No commits/pushes, tracked-file edits, workers, inference, benchmarks, server restarts, live patches, daemon/config changes, cache flushes, installs, model downloads or hardware tuning.
- SSH was to **forge only**, for file/metadata inspection and `docker exec` read-only operations. No personal inference logs, credentials, memory, transcripts or request text were collected. Container environment output was explicitly allowlisted for technical serving knobs; PID 1 arguments were filtered to serving flags.
- All writes are under `artifacts/astra-perf-20260905/`. Local temporary test directories were created there and removed by the tests.
- Read all required starting files, including both benchmark harnesses, the live audit, launcher snapshot, both READMEs, and sweep summary. Inspected the staged runtime patch scripts, installed sources and selected public upstream changes.
- Live launcher SHA256: **`f44302e9a676c0c88f02c3a04aa35788709131036e11c7554b29d9c8cf7410c7`**, identical to the supplied snapshot.
- Head container image ID: **`sha256:0f0fec9b56600c8df43d94a4b20bfdf2ae139986d1a19a16f672e13fd8090b42`**, running, started `2026-09-04T20:29:36.449774636Z` at inspection.
- Recipe checkout: `79f10b91f84779b2b1ff2c9327b1a5847cd97f70`; E2 build checkout and repository `UPSTREAM-COMMIT.txt`: **`eb0469fbb2b49fd7c025f594a3339a121e58f7a9`**. Do not assume the recipe overlay's `exl3.py` is the installed E2 implementation: the copied files differ.
- Installed package identifies vLLM **`0.1.dev20051+g487ecf187`**; image build pins ExLlamaV3 **`c5d9c657966ffeeaa9353f0cc899f18629da4a13` / 0.0.43**. The Python overlay already accommodates a newer 30-argument MoE ABI, but the live binary has 29 arguments.
- Only the head container's installed source/binary was examined. All-rank digest, source and effective-geometry agreement remains a required next-window check, not a fact established here.

### Evidence path notation

All relative paths below are within this artifact directory unless they explicitly refer to repository files:

- **`I/` = `installed/`**: source copied from `/usr/local/lib/python3.12/dist-packages/` in the head container, plus selected `/opt/glm53` overlay files.
- **`H/` = `host/`**: copies of forge's launcher, `/tmp` staged patches and recipe overlay.
- **`U/` = `upstream/`**: selected public source/API receipts.
- Line numbers refer to these unmodified source snapshots, not candidate output.

## 1. Actual serving path

### Launcher and effective arguments

`runtime-identity.txt`, `actual-serve-argv.json` and `model-geometry.json` record the read-only receipts. Effective head arguments include TP4 / four nodes, max sequences 4, max batch tokens 7168, max context 1,000,000, EXL3, target KV `fp8`, async scheduling, DFlash k=7 with probabilistic draft / standard rejection and draft KV `auto`. `GPU_MEM_UTIL=0.80`, EXL3 fused/fat/batched/sorted enabled, row tiles off, fused temp rows 128, mixed-prefill `skip`, `SMALL_OK=2048`, spin window 16 ms, indexer workspace `stock`, retention interval 0, NCCL 2.30.7 preload / IB / GID auto-detect; **no NCCL_ALGO or NCCL_PROTO override**.

The outer launcher is not executable investigation tooling: its preflight kills containers/processes and attempts cache flushes. It was **read, never invoked**.

Two deployment integrity discrepancies:

- `H/home/jun/launch-glm53-exl3-tp4.sh:68,147` defines/consumes the long-prefill threshold, but the Docker `-e` list does not forward it. `H/tmp/glm53-exl3-start.sh:33` conditionally adds the flag only if nonempty. `actual-serve-argv.json` verifies **flag absent**. `I/vllm/config/scheduler.py:70` defaults to **0**.
- `apply_patch` at launcher line 177 ends in `|| true`. In particular `/tmp/patch_exl3_fat_kernel.py` is a **build-time installer requiring two arguments**, while startup calls it with none. It cannot install the kernel that way; the built image already supplies it. Its usage failure is swallowed. Patch-script invocation is not proof of installed state. `compiled-extension-abi.txt` proves fat GEMM and scatter symbols exist without importing Torch or executing CUDA.

### Scheduler → V2 runner → target → rejection → draft

- GLM5Next is in the default V2 architecture list (`I/vllm/config/vllm.py:77–99,630–710`). No container override selecting V1 was present. The supplied geometry is `Glm5NextForConditionalGeneration`; the installed DFlash2 factory is the V2 `gpu/spec_decode` path. The older `v1/spec_decode/dflash.py` is **not the correct primary path to optimize here**.
- `I/vllm/v1/engine/core.py:650–744` schedules and manages nonblocking execute/sample futures; `I/vllm/v1/executor/multiproc_executor.py:336–427` sends the RPCs.
- `I/vllm/v1/worker/gpu/model_runner.py:1155–1205` gathers per-request CPU state and detects uniform decode; `1518–1585` selects graph/padding and builds input/attention state.
- Target: 45 layers, first 3 dense, **42 routed-MoE layers**, 288 experts/top-8, hidden 4096, expert intermediate 2048 globally / 512 at TP4. There are 34 linear-attention and 11 sparse-attention layers (`model-geometry.json`). EXL3 column-shards gate/up and row-shards down; it is not an expert-parallel all-to-all deployment.
- Target logits and rejection sampling run at `gpu/model_runner.py:1445–1472`. Output D2H copying is deliberately started **before** the next proposal to overlap it (`1861–1897`), not an unconditional device-wide synchronization before drafting.
- DFlash2 loads five Qwen-style noncausal SWA layers (window 2048), consumes auxiliary target layers `[5,14,24,33,42]`, drafts seven positions from eight query slots per request, computes top-16 candidates and runs the selector walk. See `I/vllm/v1/worker/gpu/spec_decode/dflash/speculator.py:328–469`, `dflash2/speculator.py:215–250` and `I/vllm/model_executor/models/qwen3_dflash2.py:288–298`.

### Drafter-group is KV layout, not a TP group

`patch_glm5_drafter_group.py` changes `v1/core/kv_cache_utils.py`: partition exact SlidingWindowSpec layers, append a draft cache group, choose exact-fit or compact-64 padded slot-sharing and account for shared/standalone pages. This is primarily **boot layout/admission/capacity code**, not an extra per-layer communication operation named “drafter group.” Its version-specific comments are not proof of current per-rank geometry.

Separately, `I/vllm/v1/worker/gpu/spec_decode/dflash/utils.py:14–55` changes draft attention/cache configuration but **does not replace `parallel_config` with `speculative_config.draft_parallel_config` or enter a separate TP group**. `I/vllm/model_executor/models/qwen3_dflash.py:180–204` uses `get_tensor_model_parallel_world_size()` for Q/KV heads and row-parallel output. The requested TP1 is parsed in speculative configuration, but the inspected V2 loading path does not consume it. Source-derived expectation: each rank runs TP4 draft shards, with draft attention-output and MLP reductions. Confirm actual `tp_size`, Q/KV heads, lm_head shard shape and group membership on all ranks at the next approved boot, without dumping weights.

## 2. Hot-path findings: established source behavior vs hypotheses

### A. Fat-prefill misdispatch: refuted for the expected pure-decode shapes

`I/vllm/model_executor/layers/quantization/exl3.py:1070–1129`:

1. GPU route mapping → argsort → gather sorted token/weight lists → scatter-add expert counts.
2. One graph-safe fused `exl3_moe` launch **and return when `tokens <= cap`**, where cap is allocated temp dimension 128.
3. Only beyond that guard does E2 stage counts D2H, launch thin experts, then `count_stream.synchronize()` and read host counts (`1131–1164`). Actual fat kernels require at least one expert with **more than 128 rows**. A batch >128 alone is not proof that a fat expert ran.

For k=7 and C≤4: expected verifier rows C×8 = **8,16,24,32**. Counts per expert cannot exceed rows with unique top-k routing, so these fit the fused path. The 256 route assignments at C4 (32×8) are **not 256 verifier rows**.

`I/vllm/config/vllm.py:1916–1970` sizes graph capacity with `max_num_seqs * (1+num_speculative_tokens) * 2`, capped by 512 and MNBT: **64 here**. V2 graph descriptors round decode tokens to query-length multiples and cap requests at 4 (`gpu/cudagraph_utils.py:224–267`). This is not the common “graph maximum only 8 while verification needs 32” defect.

SM120 attention is a different threshold: `I/flashinfer/mla/_sparse_mla_sm120.py:72–74,402–424` documents/defines decode through 64 rows; its Python allocation guards at `628–641` use the same cutoff. The vLLM bridge pads NoPE 512→576 and uses sparse GLM geometry (`I/vllm/v1/attention/backends/mla/flashinfer_mla_sparse_sm120.py:116–183`). Expected 32-row C4 remains in its decode regime. No kernel trace was taken; this is source dispatch analysis, not observed per-step residency.

**Boundary cases to instrument:** mixed/initial/last-prefill and uneven draft batches. 33–64 rows can lose uniform FULL target-graph eligibility without hitting EXL3 fat dispatch; 65–128 can exceed default graph capacity and enter sparse-MLA prefill while EXL3 still uses its fused fast path; >128 enters EXL3's count-copy path. These are legitimate mixed-workload effects, not proof of a steady C4 defect.

### B. Graph/eager boundaries and synchronization

- Default target full-decode eligibility is supported by the sparse-MLA builder (`flashinfer_mla_sparse.py:287`), indexer (`indexer.py:784`) and GDN metadata (`gdn_attn.py:84`): `UNIFORM_BATCH`. Actual mode resolution is `config/compilation.py:1369–1490`; actual batch dispatch is `gpu/model_runner.py:1551–1561`. **Eligibility is not evidence every measured step replayed FULL.** No graph-mode histogram exists in this investigation.
- GLM auto-enables breakable piecewise graphs and disables ordinary torch.compile (`config/vllm.py:1293–1330`). KDA `_forward` is an intentional eager break for piecewise capture (`models/glm5next/nvidia/kda.py:356–374`); sparse indexer is also decorated (`model_executor/layers/sparse_attn_indexer_kpool.py:242`). Removing those breaks blindly risks stale prefill/state data. They do not imply uniform FULL decode is disabled.
- DFlash query graphs only run if FULL decode is requested and draft attention supports it; otherwise the speculator explicitly falls back to eager, **not piecewise** (`dflash/speculator.py:110–132`). Query graphs encompass the DFlash2 `_generate_draft` override, including candidate computation/selector.
- **DFlash context projection/cache insertion remains outside the query graph on every step** (`dflash/speculator.py:401–420`). It already fuses KV projection across five layers (`qwen3_dflash.py:452–458,525,552–603`); proposing “fuse the five GEMMs” would rediscover an existing optimization. A fixed-shape pure-decode precompute graph is still a potential optimization.
- Pure EXL3 decode does not call `.item()` for active-expert count: the adapter passes -1 if the ABI supports it, otherwise uses 29 args (`exl3.py:589–600,1113`). Do **not** enable dynamic group sizing by inserting a GPU count `.item()` per layer.
- E2 prefill has a real stream synchronization and Python expert loop (`exl3.py:795–910,1152`); sorted/legacy alternatives have additional host-dependent work. Draft metadata's `.max().item()` at `dflash/speculator.py:332` reads **CPU** upper-bound sequence lengths, not a GPU tensor. Grepping `.item()` alone misclassifies it.
- `gpu/spec_decode/utils.py:47–48` synchronizes a draft-token D2H copy when collecting its result; this is separate from per-layer kernels. Boot/profile/capture `torch.accelerator.synchronize()` calls in the runner are not steady-decode barriers.

### C. Per-rank communication and the first candidate

Target attention row-parallel outputs and the combined MoE output reduce across TP. `I/vllm/model_executor/layers/linear.py:1653–1654`; `fused_moe/runner/moe_runner.py:468–487`; `distributed/parallel_state.py:662–710`. Drafter Qwen layers also contain row-parallel reductions as described above. DP=1/PP=1 paths should not be counted as extra DP/PP network collectives merely because their code exists.

**An avoidable large collective:** `qwen3_dflash2.py:291–297` calls `candidate_logits_processor(...)`, which `_apply_head`s a vocab shard and `_gather_logits` across TP before top-k (`logits_processor.py:84–96,135–153`). Platform default uses all-gather (`platforms/interface.py:1117–1122`). Current C4 drafter sampling has 4×7=28 rows and vocabulary 154,880, yet needs 16 candidates/row.

Analytical payload comparison, **not a measurement**: 4,336,640 gathered score elements, about **8.27 MiB** if two-byte scores; reducing local top-16 values+int64 IDs yields 28×4×16 entries, about **17.5 KiB** combined logical payload at that dtype. There are two smaller collectives rather than one large one. Local lm_head GEMM cost and downstream dense rejection-logit storage remain; communication need not dominate wall time. C1 may be latency-bound and see no gain or regress.

### D. Decode-floor and spinwait

`I/vllm/v1/core/sched/scheduler.py:12–50,568–576,952–963`: the helper reads environment/parses integers and scans peers even for decoders, but its return is applied only to requests still prefilling. Thus **no pure-decoder token-budget throttling is introduced by this helper**. CPU overhead remains possible but unmeasured; with max four requests this is not evidence for a 2× loss.

`I/vllm/distributed/device_communicators/shm_broadcast.py:134,191–214`: 16 ms is a busy/yield window **since the last read**, followed by a notification poll. It is not a 16 ms sleep added to every step. Longer C4 steps could change spin/poll frequency and wakeup jitter; only paired tests can tell. This is local RPC coordination, not an NCCL algorithm setting.

## 3. Public upstream and prior attempts

Selective public retrieval receipts are in `public-audit-commands.txt` and `U/`; no checkout update was performed.

- **MiaAI recipe:** public HEAD **`3021f24c88a0904c768c46ff22a508407e31360a`**, compared with E2 pin `eb0469f...`: two commits, **issue/PR templates only**. No newer hot-kernel fix in that delta (`recipe-compare.json`). Blindly upgrading this recipe cannot explain a speed gain.
- **vLLM:** fetched public HEAD **`32601ef7a1ce8aaa6d777778435ec499248906fb`**. `U/vllm-latest-logits_processor.py:253–301` supplies distributed top-k; `vllm-latest-qwen3_dflash2.py:282–289` uses it. **Semantic trap:** latest code selects first, converts values to fp32, scales, then softcaps; installed `LogitsProcessor.forward` softcaps then scales in the existing dtype. Candidate preserves the installed order/dtype and transforms before selection. No FlashInfer radix-topk helper/dependency is introduced.
- vLLM DFlash path history was checked (`vllm-dflash-history.json`): PP support and draft-specific RoPE fix are distinct changes, not blanket speed backports. XGrammar `12f64b39...`/`c6e19b3...` backports are already in the recipe; retain them.
- **ExLlamaV3:** public **`d5e4361fd5d77b5d7d64ed2744595f2d6359c1bd`** replaces fixed round-robin with dynamic tickets and adds optional active-count launch sizing. Relevant six extension files were inspected. Current installed source bytes match the curated pristine pin **for all six files**; `nm -D -C` confirms live `exl3_moe` ends in `float` (no extra active-count int). The upstream Python `block_sparse_mlp.py` hunk is not used by vLLM and is excluded.
- **Reederey87**, pinned review at **`8133af321fe52d299b8492444643f4cb80e413e5`**: curated ticket backport and three-stage fat-GEMM cp.async implementation inspected. Their `docs/11` explicitly says ticket decode rebench **PARITY**, and fat-kernel ~41% microbenchmark gains have **unresolved end-to-end benefit** (full-set prefill median ~+0.3% under contention). These are external receipts, not our measurements and not evidence for a TP4 speedup. Their rewritten fat kernel is not a drop-in replacement for MiaAI's different E2 kernel without revalidation.

Public links:
- https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks/compare/eb0469fbb2b49fd7c025f594a3339a121e58f7a9...3021f24c88a0904c768c46ff22a508407e31360a
- https://github.com/vllm-project/vllm/blob/32601ef7a1ce8aaa6d777778435ec499248906fb/vllm/model_executor/layers/logits_processor.py
- https://github.com/turboderp-org/exllamav3/commit/d5e4361fd5d77b5d7d64ed2744595f2d6359c1bd
- https://github.com/Reederey87/glm53-flash-exl3-2x-dgx-spark/blob/8133af321fe52d299b8492444643f4cb80e413e5/docs/11-gb10-kernel-program.md

### Historical/dead-end ledger, not a causal ranking

Retain the known constraints: no forced NCCL Tree/LL128 or Tree/Simple (failed); Ring/LL128 booted but was not properly benchmarked; preserve autotune. No MNBT 8192 (indexer smem); no cold-JIT long-prefill stress without staged preparation; no memory utilization >0.80 (driver OOM history). Prior k=8 hurt prose, k=7 is adopted; don't conflate k sweeps with code changes. EXL3 row tiling and enlarged fused temps have negative receipts; no reason to assume a cap change helps 32-row decode. Workspace `rightsize` is a capacity/sizing proposal, not an established decode accelerator, and remains off.

The September 4 sweep measured one scored run per boot: baseline 106.4; async-off 115.0; MNBT1024 119.6; skip-drafter 134.4; skip-spinwait 131.8; skip-floor 135.8 aggregate tok/s. Those are **existing measurements only**, not replicated here. The harness itself performs a short C4 warmup, so “cold” means first scored run after boot, not literally zero warmup.

Critically, `U/image-build.txt:468,470,477` bakes drafter-group and decode-floor but only preflights spinwait. `SKIP_PATCHES=patch_glm5_drafter_group.py` normally leaves the baked layout; skipping decode-floor leaves the baked policy and omits `SMALL_OK`; skipping spinwait can genuinely preserve the stock spin duration on a fresh image. Historical installed-file receipts would be needed to prove exactly what each old arm did. **The summary's claim that the regression is collectively caused by the patch set is unsupported.**

Treat **253 aggregate on Aug 28**, **128.9 C-verified on Sep 3**, and **106.4 first-scored-after-boot baseline** as separate dated observations. A common harness name is not a paired baseline. Template, effective args, cache/compile warmth, draft acceptance, co-tenancy and boot variability matter. Do not claim either candidate restores 253.

## 4. Ranked candidates (five; all unmeasured here)

### 1 — Distributed DFlash2 top-16 candidate collection: first experiment

- **Location:** `I/vllm/model_executor/models/qwen3_dflash2.py:288–298`, `I/vllm/model_executor/layers/logits_processor.py:135–153`; new helper in `candidate-topk/.../logits_processor.py:207`.
- **Mechanism:** per-rank local top-16 → small values/IDs all-gathers → global top-16. Same weights, k, target sampling/rejection and candidate score transform. Likely most relevant to C4; C1 may pay more collective latency; prompt-only prefill mostly unaffected, mixed traffic may shorten draft steps.
- **Falsification:** verify actual draft TP>1; time candidate projection/collection separately. If candidate collective time falls but overall iteration time does not, or C1 regresses, don't call it a win. If topology is TP1 or candidates/scores fail correctness gates, stop.
- **Risks:** BF16 ties/top-k tie ordering can change candidate sets or selector paths; shard padding/added vocabulary; two collective launches; graph capture and all-rank ordering. The baseline top-k itself has no stable tie guarantee. Candidate intentionally scopes to this unchanged-vocabulary/no-LoRA lane. Do not silently accept changed stochastic output distributions.
- **Rollback:** omit/revert the two Python-file patch in a clean experimental image; return to frozen A image/config. No independent package upgrade.

### 2 — Ticket scheduler, six-file extension-only backport

- **Location:** current `I/exllamav3/exllamav3_ext/quant/exl3_moe_kernel.cuh:46–59` assigns active experts modulo concurrency. Candidate replaces it with tickets; `exl3_devctx.cu:65` gains scheduler state, `.cuh:11–15` defines +66 ints; patched kernel reset uses acq_rel retirement at lines 268–279.
- **Mechanism:** groups claim the next expert instead of waiting on an uneven fixed assignment. C4 heterogeneous routing is plausible; C1/thin prefill may be parity. Fat GEMM itself unchanged. Keep `num_active=-1`: no extra D2H count and no active-count widening experiment.
- **Falsification:** compare fused-MoE kernel elapsed distributions and iteration tails on identical rank-sliced routes, then paired C1/C4. If no within-kernel benefit, do not infer benefit from noisy client timing. External same-kit C1 parity lowers confidence.
- **Risks:** device-global scheduler reset/barrier correctness, shared-stream concurrency assumptions, changed floating-point accumulation order, ABI/rebuild/all-rank consistency. Run graph replay and sanitizer gates before serve.
- **Rollback:** previous image digest; this is a compiled change, not a runtime flag. Curated installer has an explicit build-time opt-out; never copy a new `.so` into a live process.

### 3 — Capture only DFlash context precompute for stable pure-decode shapes

- **Location:** `I/vllm/v1/worker/gpu/spec_decode/dflash/speculator.py:401–420`, `qwen3_dflash.py:552–603`.
- **Mechanism:** graph the already-fused context norm/KV projection/RoPE/cache insertion for stable C×8 rows and persistent slot/context buffers. Leave prefill/varlen eager and keep the existing query graph. Potential C1/C4 CPU/launch saving; no large-prefill speed claim.
- **Falsification:** measure eager precompute's CPU/GPU share first; no meaningful share means reject. Verify identical cache writes and rejection rollback across acceptance 0…7, sequence admission/retirement, prefix reuse and block boundaries.
- **Risks:** stale captured pointers, padded/rejected slots overwriting KV, additional graph memory/pool aliasing. Do not capture arbitrary `context_slots` Python lists or bypass KDA/indexer breaks.
- **Rollback:** feature-gated fallback to the current precompute call. No KV layout or context reduction permitted. No candidate implementation supplied: less bounded than #1/#2.

### 4 — Port fat-GEMM cp.async pipelining, not a whole kernel-stack upgrade

- **Location:** `I/exllamav3/exllamav3_ext/quant/exl3_fat_gemm.cu`; external example `U/reederey-ticket/overlay/exl3_fat_gemm.cu:69–143,273–275`.
- **Mechanism:** overlap packed-weight/activation loads with MMA through a three-stage pipeline. **Prefill only**, and mixed batches with real fat experts; pure C1/C4 verification should be unaffected.
- **Falsification:** benchmark actual TP4 gate/up/down shapes (intermediate 512, not TP2's 1024), profile fraction in fat GEMM, and require end-to-end cold-prefill improvement in paired runs. External ~41% kernel-only gain is not a predicted serve gain.
- **Risks:** predicated cp.async on Blackwell, tail masking, smem/occupancy, scatter accumulation and sanitizer failures. Existing E2 layout differs from the external implementation.
- **Rollback:** previous E2 image; retain existing persistent scratch and memory ceiling. No live JIT or source swapping.

### 5 — Forward the missing long-prefill threshold (mixed-latency correction)

- **Location:** launcher line 68 and Docker env list near line 245; inner line 33. Minimal proposal: forward `-e LONG_PREFILL_TOKEN_THRESHOLD=$LONG_PREFILL_TOKEN_THRESHOLD` in a separately versioned test launcher, keeping 1792.
- **Mechanism:** enforce the intended cap when no decode-floor exemption blocks a prefill; shorter prefill steps improve opportunities for newly arriving short requests. **Not a pure C1/C4 decode accelerator.** Smaller chunks can reduce solo prefill throughput.
- **Falsification:** assert flag/parsed scheduler threshold 1792, measure actual scheduled chunk sizes and short-arrival TTFT during a long prefill, plus solo prefill throughput. No benefit to the intended QoS or unacceptable solo regression → don't adopt blindly.
- **Risks:** a real scheduling change despite looking like a config repair; interaction with hybrid alignment, `SMALL_OK` and JIT shapes. Keep separate from #1's A/B.
- **Rollback:** frozen original launcher/image/arguments. Do not “fix” this unnoticed inside a kernel experiment.

## 5. Exact next experiment and approval gates

**Proposed for Depths; none of this serving work was executed.**

1. **Freeze A as actually running**, not as documented: same model/drafter files, template, TP/world size, k=7, batch7168, four sequences, current graph configuration, threshold currently absent, skip/small2048, retention0, indexer stock, spin16, all patch post-states, NCCL autotune/preload and GPU_MEM_UTIL=0.80. Save all-rank code/image hashes and numeric runtime geometry. Existing head receipts here seed that manifest.
2. **Harness hygiene first:** standalone executable harness output must go to a new run-ID directory, not `bench_decode_full.py`'s hardcoded dated output. Use the C4 steady ruler (4×1600, code+exhaustive tests, temp0, thinking off) with actual usage counts. Assert exactly four successful results, usage present, finish reasons and requested token lengths, coordinated launch, server request-count isolation and no unrelated workload. The current C4 code silently excludes failed thread results; correct this before comparing.
3. **Repeated A:** identical warmup until shape/JIT work is quiet; at least five scored C4 rounds on the same pinned prompt/nonce corpus, reporting each round, median and spread. Preserve caches; distinguish prompt cold/warm from JIT warm. Count requests/counter deltas so other traffic invalidates a round. Record TTFT, full-window token rate, true four-active overlap rate and per-stream decode latency separately. No cache flush on the shared serve.
4. **Pre-serve correctness gate for #1:** in an approved isolated maintenance/test environment with existing weights, validate the two patched Python files against installed Torch: TP1/TP4, C1–C4 shapes, vocabulary padding, ties at and across top-16 cutoff, large-magnitude/softcapped scores, greedy and nonzero-temperature sampling. Compare global candidate IDs and scores to full gather; explicitly investigate ties rather than hiding mismatch. Validate selector probabilities/rejection outputs, actual dtype, numeric finiteness, graph capture/replay and all-rank collective order. Stochastic correctness and structured/tool/thinking behavior are release gates. Local source tests here do not replace these.
5. **Build B with only #1**, same base/dependencies/CUDA extension and all serving knobs. The draft candidate files go in a new experiment image, identical on all ranks. Do not stack the ticket patch, threshold repair, TP1 rework or workspace tuning. Keep a known-good A image available. Any restart/traffic requires Depths approval and supervised maintenance; coordinate watchdogs explicitly, never race automatic relaunch. Use existing or separate named warm compile caches, never delete the production cache.
6. **Paired repeated A/B/A**, same warmup per boot and same request corpus; ≥5 scored C4 rounds per phase, with C1 structured/code/prose controls and spec-counter deltas per phase (not lifetime ratios). Repeat the reversed pairing if a promising result appears. Save per-rank memory/OOM/thermal/clock telemetry **without changing it**. A1/A2 medians should agree within a prespecified 5% noise band; otherwise extend/repeat, not declare victory. Suggested decision threshold: reproducible ≥5% C4 gain exceeding baseline spread, paired uncertainty excluding no gain, no material C1/TTFT/correctness regression. This threshold is a proposed rule, not a measured variance estimate.
7. **Mechanism instrumentation:** fixed numeric-only counters/timing ranges for target graph mode and padded rows, drafter TP/shard sizes, candidate collection, context precompute, query graph and EXL3 branch. GPU events/short profiler traces belong only to the approved experiment and must be symmetric or excluded from scored runs. No prompt/token text logging. Require the expected large gather to disappear; otherwise the intended code path wasn't exercised.
8. **Safety soak and mixed guards:** short sanity → modest cold prefill → ~100k controlled prefill with short arrivals → larger context guard only after no sustained per-rank OOM or corruption. Preserve 1M context capability, weights/quant, drafter distribution, NCCL autotune and utilization ≤0.80. Do not invoke an unreviewed launcher merely to test syntax. On correctness failure, deadlock, sustained OOM or >5% control regression, stop and return to A; no live hot patch. A result below the decision bar is inconclusive/no-go, not permission to retain an optimization because it sounds better.

Why no immediate attempt to recreate 253: the first question is whether B beats a repeatable **current effective A**. A separate historical reconstruction needs archived image/launcher/harness/template receipts and its own paired baselines. Single cold-boot ablations do not establish a collective cause or justify removing safety/capacity patches.

## 6. Local deliverables, verification and remaining risks

### Candidate artifacts (unapplied)

- **`candidate-dflash-distributed-topk.diff`** — two-file trial patch; generated full candidate sources under `candidate-topk/`. Preserves installed cap-then-scale and dtype, uses existing Torch topk/TP all-gather, no new dependency. No CUDA/PyTorch execution has validated it.
- **`candidate-ticket-only.diff`** — six-file extension patch against the exact installed source; intentionally excludes upstream Python and intervening commits. Curated pristine/patched bytes and installer are under `U/reederey-ticket/overlay/`.
- `build-topk-candidate.py`, `verify-investigation.py`, `audit-public.py`; evidence snapshots and `source-manifest.sha256`.

### Commands actually verified

Receipts: **`verification.txt`**.

- `python3 -B artifacts/astra-perf-20260905/verify-investigation.py`: **9 tests passed**. Covers launcher byte identity/missing forwarding, baked patch confounds, pure-decode floor guard, dispatch bounds, draft loader retaining target parallel config, all six ticket pristine byte matches, ticket installer opt-out/idempotence/drift/mixed-state refusal on artifact-only temp files, current adapter's 29/30-arg/-1 handling, candidate syntax and top-k mathematical reference property.
- `patch --dry-run -p1` against the installed snapshots: **both candidate diffs match all intended files**. Nothing applied to those snapshots or the container.
- `bash -n` on copied outer/inner launch scripts: **passed**; neither script executed.
- `nm -D -C` on the head installed extension: fat GEMM/scatter exist; MoE ABI is the original 29-argument form. No Torch/CUDA initialization for this check.
- `git diff --exit-code`: no tracked working-tree differences. Final HEAD/status check preserved the public pin; the only untracked top-level entry was the pre-existing artifacts directory.

**Limits:** no local Torch/NumPy/pytest was installed or available; the math reference test is not a tensor-implementation or GPU correctness test. No CUDA compile, sanitizer, graph capture, inference, performance profile, all-rank live-source audit or historical arm reproduction was attempted. Some source-discovery guesses were absent (e.g. `gpu/output.py`); actual referenced runner/speculator paths were located and copied instead. No missing tool blocked the read-only investigation.

The primary residual risks are tied-score/stochastic correctness for #1; scheduler-reset/ABI correctness for #2; KV aliasing for #3; asynchronous copy/tail correctness for #4; and prefill/QoS tradeoffs for #5. Further “true draft TP1” work is deliberately not bundled into these candidates. All speed predictions remain hypotheses until controlled paired measurement.
