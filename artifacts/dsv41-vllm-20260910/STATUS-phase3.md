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
