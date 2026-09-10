# REPORT — Phase 3: DeepSeek-V4.1-Flash on vLLM (TP4, DSpark) across 4× DGX Spark

**status: success**

**Final state: a vLLM TP4 world with working DSpark is SERVING and left running** at `http://192.168.10.1:8000/v1` (model `deepseek-v4.1-flash`, max_model_len 300000, KV pool 1,374,757 tokens). Containers `vllm_dsv41` on all 4 nodes (forge/anvil/ember/flame), auto-restart armed **after** the API+spec gate passed. All correctness gates pass **with DSpark speculative decoding ON** — including the exact tool round-trip that corrupted deterministically on SGLang+DSpark. Benched both ways, comparable to Tony and to our V4 Flash numbers.

## What changed (all under /home/jun/dsv41-vllm/ unless noted)

1. `forge:/home/jun/dsv41-vllm/` — work tree: `tony/` (Tony's repo @ `ca662ac35193c69ace9cee37f13a94abf2eff0fc`, pinned boot-10, rsynced to anvil/ember/flame), `vllm-src/` (vllm branch `dsv41-feat` @ `e47aa780bccf59f59dfa2cbb18e17a10b4fe69ba`, rsynced to workers), `gpuflip/` (slow-state probes), `nccl/` (collective checks), `bench/` (both bench suites + telemetry), `logs/`, `STATUS.md` (updated at every stage boundary), `build1.sh`, `build-chain-345.sh` (reproducible image chain).
2. Images built node-local on all 4 nodes: `vllm-dsv41:overlay1→3→4→5`, final also tagged **`local/vllm-dsv41:overlay5`** (23.3 GB). Image IDs: forge `1efef58714e9…`, anvil `61d5b829c1b2…`, ember `ffaf91bab36e…`, flame `2fcf9e4c0260…` (differ per node — expected for node-local builds; the verify5 no-JIT gate is the real check, see below).
3. Patches staged `~/patches/dsv41-boot10/` on every node (7 files + `mounts.txt`), md5-verified identical to Tony's `patch/README.md`: `engram.py c0329107`, `model_state.py 0a14bee6`, `weight_utils.py 7e1027f1`, `attention.py da9ef196`, `flashinfer_sparse.py af0f8447`, `sparse_swa.py cc419353`, `sparse_attn_indexer.py a9b73756`, `mounts.txt 79a774bc`.
4. **New launcher** `forge:/home/jun/launch-dsv41-vllm-tp4.sh` (default `MAXLEN=300000`): Tony's boot-10 config translated to our fabric — full local checkpoint on every rank (`/home/jun/models/deepseek-v4.1-flash` → `/models/DeepSeek-V4.1-Flash:ro`; **no NFS, no `ENGRAM_LOCAL` needed** — every rank reads weights AND engram rows from local NVMe), rail-B ConnectX env (`enP2p1s0f1np1` / `roceP2p1s0f1` / 192.168.10.0/24, `NCCL_IB_GID_INDEX=auto`), workers 3,2,1 then head 0, stop-every-node-head-first relaunch rule, and our serving hardening: **disarmed boot → API up → spec-decode gate → only then arm `unless-stopped`**. Head-container-death early-exit in the wait loop.
5. Nothing under `/home/jun/models/` modified (all mounts `:ro`); `local/qwen38-gb10:*` and `local/dsv41-gb10:*` untouched; eva-core host service untouched; no GitHub pushes; all inference local; only one TP4 world at a time (SGLang containers were already down and stayed down).

## Exact working launch

```
MAXLEN=300000 bash /home/jun/launch-dsv41-vllm-tp4.sh   # on forge; env defaults now encode the serving config
```
Effective per-rank container (rank N adds `--node-rank N` and `--headless`, drops host/port):
```
docker run -d --name vllm_dsv41 --restart no  # armed to unless-stopped by the launcher AFTER the spec gate
  --log-driver json-file --log-opt max-size=25m --log-opt max-file=4
  --gpus all --network host --ipc host --shm-size 32g --stop-timeout 60
  --memory 112g --memory-swap 112g --oom-score-adj 500
  --device /dev/infiniband --cap-add IPC_LOCK --cap-add SYS_NICE
  --ulimit memlock=-1 --ulimit stack=67108864 --ulimit nofile=1048576:1048576
  -v /home/jun/models/deepseek-v4.1-flash:/models/DeepSeek-V4.1-Flash:ro
  -v /var/tmp/dsv41-vllm-cache:/cache
  -v ~/patches/dsv41-boot10/<file>:/usr/local/lib/python3.12/dist-packages/vllm/<site path>:ro   # 7 files per mounts.txt
  -e VLLM_HOST_IP=<node ip> -e HF_HOME=/cache/huggingface -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1
  -e VLLM_CACHE_ROOT=/cache/vllm-phase3 -e VLLM_ENGINE_READY_TIMEOUT_S=3600
  -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True -e VLLM_USE_RUST_FRONTEND=0 -e VLLM_HAS_FLASHINFER_CUBIN=1
  -e DSV41_ENGRAM_DISK=1 -e DSV41_ENGRAM_DISK_THREADS=32 -e DSV41_ENGRAM_DISK_CHUNK=16
  -e VLLM_USE_BREAKABLE_CUDAGRAPH=1 -e TORCH_CUDA_ARCH_LIST=12.1a -e FLASHINFER_CUDA_ARCH_LIST=12.1a
  -e FLASHINFER_DISABLE_VERSION_CHECK=1
  -e NCCL_NET=IB -e NCCL_IB_DISABLE=0 -e NCCL_IB_HCA=roceP2p1s0f1 -e NCCL_IB_GID_INDEX=auto
  -e NCCL_IB_ROCE_VERSION_NUM=2 -e NCCL_IB_ADDR_FAMILY=AF_INET -e NCCL_IB_ADDR_RANGE=192.168.10.0/24
  -e NCCL_SOCKET_IFNAME=enP2p1s0f1np1 -e GLOO_SOCKET_IFNAME=enP2p1s0f1np1 -e TP_SOCKET_IFNAME=enP2p1s0f1np1 -e MN_IF_NAME=enP2p1s0f1np1
  -e NCCL_NVLS_ENABLE=0 -e NCCL_CROSS_NIC=1 -e NCCL_IB_MERGE_NICS=0 -e NCCL_CUMEM_ENABLE=0
  -e NCCL_IGNORE_CPU_AFFINITY=1 -e NCCL_DEBUG=WARN -e TORCH_NCCL_ASYNC_ERROR_HANDLING=1
  -e MAX_JOBS=2 -e FLASHINFER_NVCC_THREADS=1 -e VLLM_USE_FLASHINFER_SAMPLER=0
  -e TILELANG_CACHE_DIR=/cache/tilelang -e TRITON_CACHE_DIR=/cache/triton
  local/vllm-dsv41:overlay5 /models/DeepSeek-V4.1-Flash
    --served-model-name deepseek-v4.1-flash --host 0.0.0.0 --port 8000
    --tensor-parallel-size 4 --gpu-memory-utilization 0.80 --max-model-len 300000
    --max-num-seqs 8 --max-num-batched-tokens 8192 --block-size 128
    --engram-config '{"cpu_offload": false}' --default-chat-template-kwargs '{"thinking": false}'
    --limit-mm-per-prompt '{"image":4}' --mm-processor-cache-gb 1
    --tool-call-parser deepseek_v41 --enable-auto-tool-choice --reasoning-parser deepseek_v41
    --speculative-config '{"method":"dspark","num_speculative_tokens":5,"draft_sample_method":"probabilistic","rejection_sample_method":"block","enable_adaptive_verification":false}'
    --compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE","cudagraph_capture_sizes":[5,6,10,12,15,18,20,24,25,30,35,36,40,42,48]}'
    --distributed-executor-backend mp --nnodes 4 --node-rank 0
    --master-addr 192.168.10.1 --master-port 29500
```
vLLM version serving: `0.28.1rc1.dev388+g8a728663c` (dsv41-feat python tree over the pinned merge-base nightly).

## Per-rank state (300k serving boot)

| | value |
|---|---|
| Weights per rank (DSpark draft + vision encoder) | **81.58 GiB** (matches Tony boot-10's 81.58) |
| KV pool | **1,374,757 tokens** (4.58× at 300k; Tony: 1,070,168 / 3.57×) |
| Engram rows | DISK mode, contiguous distinct per-rank ranges (layer 1: `[0,96M) [96M,192M) [192M,288M) [288M,384M)`) — rank-offset fix present and verified on all 4 ranks |
| Host memory | ~5-6 GiB MemAvailable per node while serving; `--memory 112g` never hit; swap: forge ~0.9 GB (pre-existing), workers ~0.2 GB |
| Boot time to API | ~15 min (weights 48 shards ~40 s + draft pass + autotune ~4 min + graph capture) |

## Gate results (DSpark k=5 + FULL_AND_PIECEWISE graphs ON; 131k boot, re-verified on 300k boot where noted)

| Gate | Result |
|---|---|
| Spec-decode gate | **PASS** — 39 spec counters in `/metrics` + `SpecDecoding metrics` log lines; armed after |
| Arithmetic 19+23 (thinking off) | **PASS** — `"42"`, finish=stop, reasoning_tokens=0 (both boots) |
| JSON schema strict | **PASS** — `{"answer": 42}` |
| **Tool round-trip (phase-1 SGLang corruption repro)** | **PASS CLEAN** — `lookup_fixture({"key":"alpha"})` → continuation `The value for key **alpha** is **42**.`, finish=stop. No `</tool_result>` runaway, no garbage recursion. Also: **vLLM's `deepseek_v41` parser does NOT drop tool parameters emitted without the `string=` attribute** — `{'key':'alpha'}` parsed correctly, no patch needed (SGLang's parser silently dropped them; that upstream bug report is SGLang-only) |
| corrcheck 7/7 | **PASS** (both boots) — models, nonempty, temp-0 determinism, explicit tool call, tool history roundtrip, structured JSON, thinking opt-in (17×23=391 w/ reasoning) |
| NIAH | **PASS 12/12** (32k 6/6 + 100k 6/6, actual 32,767/102,399 prompt tokens) — re-run ok:true on 300k boot |
| Vision | **PASS on content** — "A red circle on the left and a blue square on the right." Deviation note: `image_tokens==1024` assertion is SGLang-only usage accounting; vLLM returns `prompt_tokens_details: null` (prompt_tokens 905 ≈ 891 image + 14 text) |
| 5-min C4 soak | **PASS** — 122 reqs / 0 failures / 304 s; worker memory deltas flat (≤~150 MB) |
| Count-to-100 (Tony verify.txt style, 300k boot) | 80.3 tok/s after idle, 83.6 back-to-back, correct 1..100 both (Tony boot-10: 84.9 / 92.2) |

**Headline finding: DSpark speculative decoding does NOT corrupt output on this model under vLLM.** The exact second-turn tool-result continuation that SGLang+DSpark corrupted deterministically (3/3 identical md5, `</tool_result>` runaway) is byte-clean here, across the tool gate, corrcheck roundtrip, NIAH, vision, soak and both boots. This moves the phase-1/2 diagnosis from "engine-agnostic / model-boundary" to **SGLang-side verify path** — consistent with SGLang PR #38879 (DSpark verify rewrite, merged 2026-09-10 13:58 UTC, after our SGLang image was built) and the PR #33872 symptom family (closed). No vLLM-side parser patch was needed.

## Bench tables

### Tony-comparable (v41bench.py, prompt set v1 byte-identical, temp 0, thinking off, usage-block token counts, warmup first; 131k boot)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) | Tony boot-10 aggregate |
|---|---:|---:|---:|---:|
| C1 | 42.96 | 48.24 | 0.377 | 37.95 |
| C2 | 67.31 | 38.69 | 0.463 | 64.30 |
| C3 | 80.50 | 30.89 | 0.472 | 78.70 |
| C4 | 108.66 | 31.39 | 0.453 | 85.72 |
| C5 | 124.54 | 29.48 | 0.741 | 114.20 |
| C6 | **132.01** | 25.77 | 0.515 | 131.86 |

Per-stream decode by category: code C1 **70.59** (Tony 73.8), counting ceiling 55.9-71.5 (Tony 33.4-62.2), prose 13.8-33.5, narrative 10.4-29.8. Cold prefill: 2k/8k/32k/64k = **1079 / 811 / 1524 / 1448 tok/s** (Tony: 902/1026/1539/1194). Files: `bench/bench-phase3-131k.{json,md}`; drift check on the 300k boot: C1 43.04/48.71 (within 1% of the 131k boot).

### V4-Flash-comparable (spark-bench protocols, same fabric)

| metric | DSV4.1 Flash (vLLM, this run) | V4 Flash record (vLLM+MTP) |
|---|---:|---:|
| C1 record protocol, 2048 tok, code (`bench-decode.py`) | **median 62.88** (mean 59.14, sd 10.07, min 47.6, max 74.8) | 136.25 median (145.5 peak) |
| 5k prompt (`bench-depth.py`) | median 41.8 | ~79-93 (code) / 72-89 (prose) |
| 10k prompt | median 42.6 | — |
| C4 aggregate | 136.7 (4 streams) | 182 |
| DSpark/MTP acceptance | C1 window p50 5.24 tok/step; v41bench window mean 4.12 (156 windows) | ~4.6-4.9 code / 2.1-2.4 prose |

**GPU slow-state (Tony issue #1): never observed on this fleet.** Two idle gpuflip probes (all 4 nodes concurrently) + pre-boot flipsum: all-fast 60/60 shared seconds, zero slow seconds; gemv_cont p50 217-219 GB/s, mm_duty 81-84 TFLOPS, clocks 2171-2190 MHz, 18-25 W. Telemetry during benches (anvil/ember/flame CSVs, 2 s samples): clocks pinned 2177-2190 MHz p10-p90, max power 36-42 W decode. The 2200 MHz `spark-gpu-clock-lock.service` on all 4 nodes stayed active throughout. (forge's own bench-window CSV was lost to a sampler redirect bug — noted below; 3/4 nodes + both idle probes cover the state.)

## Deviations from Tony's recipe, and why

1. **No NFS anywhere; no `ENGRAM_LOCAL` copy step.** Our checkpoint is local on all 4 nodes (sha256-verified in phase 1), so every rank reads weights and engram rows from local NVMe — strictly better than Tony's NFS + per-worker sparse-copy path. Verified: `engram.py`'s `_dsv41_engram_local_dir` returns plain `model_dir` when `DSV41_ENGRAM_DIR` is unset; per-rank DISK-mode log lines show correct contiguous row ranges.
2. **Fabric translation**: Tony's 192.168.192.0/24 / `enp1s0f0np0` / `NCCL_IB_GID_INDEX=3` → our rail B 192.168.10.0/24 / `enP2p1s0f1np1` / `roceP2p1s0f1`, plus `NCCL_IB_GID_INDEX=auto` (our ember/flame GID-drift lesson) and `NCCL_CROSS_NIC=1` (our SGLang launcher value).
3. **Image-ID check relaxed to warn-not-fail** (node-local builds legitimately differ; verify5-style no-JIT check is the real gate, per the recipe's own note).
4. **Disarmed-boot → gate → arm** hardening ported from our spark-bench pattern (Tony boots with `--restart no` and does not arm).
5. **cmake pip-installed into the build container** (Tony's `build_stable_ext.sh` assumed it present; the nightly image ships nvcc+ninja but not cmake).
6. **verify5 semantics note**: in FlashInfer 0.7.0rc1, `try_load()` always returns `None` for JIT specs (by design — it defers to ninja, which no-ops). The printed "VERIFY mxfp8: MISS" is therefore expected; the real no-runtime-compile gate was verified directly: `build_and_load()` in 1.4 s (ninja no-op) and `sparse_mla` 0.0 s, matching Tony's documented "1.5 s / 0.0 s, no compile".
7. **Vision gate scoring**: content-correct PASS; the `image_tokens==1024` assertion is SGLang-specific usage accounting, which vLLM does not expose (see gate table).
8. MAXLEN staged 131072 (gates) → 300000 (final serving config, launcher default updated), per handoff.

## Remaining risks / follow-ups

- Host memory headroom while serving is ~5-6 GiB per node (same shape as Tony's boot-10 and our SGLang p2 under load). Tony's recommended host hardening (`dgx-anti-oom` regex, `vm.min_free_kbytes=1048576`, `watermark_scale_factor=200`) is not applied on our fleet — system-setting changes left for a human decision.
- The C1 sd of 10 tok/s (47.6-74.8 spread) mirrors Tony's observation that DSpark acceptance and/or GPU state can move a single cell ~1.5×; we measured with clocks locked and no slow state observed, so we attribute it to acceptance variance, not clocks.
- 1M context untested on this stack (Tony validated the top-k fix only to 300k rows). MAXLEN=300000 is the proven serving point.
- forge's bench-window telemetry CSV was lost (sampler script wrote to /dev/null — script fixed and committed to `/tmp/tel-sample2.sh`; remaining nodes have full coverage).
- First boot of the 131k world ran the full v41bench at `max_model_len=131072` (bench prompts ≤64k, so no truncation; prefill sweep unaffected).

## Rollback

```bash
# stop the vLLM world (head first), then relaunch SGLang p2 (spec-off) — lane preserved untouched:
for h in 192.168.10.1 192.168.10.2 192.168.10.3 192.168.10.4; do
  ( [ $h = 192.168.10.1 ] || ssh $h ) docker rm -f vllm_dsv41
done
bash /home/jun/launch-dsv41-tp4.sh          # SGLang p2, SPEC=0 default, on forge
# or restore the qwen world: /home/jun/qwen38-tuning-20260906/rollback-serve.sh
```
SGLang lane (image `local/dsv41-gb10:p2`, launcher `/home/jun/launch-dsv41-tp4.sh`) was not modified or deleted.

## Attribution

- **Tony (tonyd2wild)** — the recipe, the seven patches, the image chain, and the GPU slow-state finding (issue #1); repo pinned at `ca662ac` (boot 10).
- **Kai** — the SM12x page-size patches and the first Engram-on-disk patch (both carried inside Tony's patch set).
- **vLLM team** — the day-0 `dsv41-feat` branch (served as `0.28.1rc1.dev388+g8a728663c`).
- **DeepSeek** — the DeepSeek-V4.1-Flash checkpoint.
- Phase-1/2 groundwork (local checkpoint, gates, DSML-parser finding, SGLang DSpark corruption matrix): our earlier worker sessions (`depths-dsv41-nvme-port-20260910`).

## Verified-work check lines (one per claim)

- SGLang world down, memory free: `docker ps` on all 4 nodes → no running dsv41 containers; `free -g` → 116-117 GiB avail each (observed 17:0x).
- Tony repo pinned: `git rev-parse HEAD` → `ca662ac35193c69ace9cee37f13a94abf2eff0fc`.
- Base images exist: `docker manifest inspect` OK for `nightly-8a728663c1c3…` and `deepseekv41-flash-0909-arm64` (both).
- dsv41-feat branch: `git ls-remote` → `e47aa780bccf59f59dfa2cbb18e17a10b4fe69ba`.
- GPU slow-state probe (idle, ×2 runs): `flipsum.py` → `anvil/ember/flame/forge … fast 61-62s slow 0s`; `shared seconds 60: all 4 fast 60s, at least one slow 0s`; gemv_cont p50 217-219 GB/s.
- overlay1 build: `build1-forge.log` → `configure rc=0`, `[82/82] Linking CXX shared module _C_stable_libtorch.abi3.so`, `build rc=0`, `.so 29,221,144 B copied into vllm/`, `overlay1: fad2073af1e6 22.3GB`; same on 3 workers (`build1 done 17:35-17:36`).
- overlay chain: `chain-<node>.log` on 4 nodes → `overlay3 done`, `build rc=0 secs=74-78 minAvail=90-92GiB` (no boot-3 wedge), `overlay4/5 done`, final `local/vllm-dsv41:overlay5` 23.3 GB ×4.
- No runtime JIT: in overlay5 container → `mxfp8 build_and_load: 1.4s ffi.Module(imports_=())`, `sparse_mla load: 0.0s` (no compile; matches Tony's 1.5s/0.0s doc).
- Patches staged: `md5sum` on 4 nodes → all 8 md5s identical to `patch/README.md` (line of md5s reproduced above).
- NCCL pre-launch: `nccl/forge.txt` etc. → 4 ranks lockstep, `graph step 88 AR + gaps p50=57.98ms slow=0%`, `collective cost/step 4.36-5.69 ms`.
- Boot healthy: `boot300k-launch.log` → `API is up`, `OK: speculative decoding live (metrics spec matches=39, log SpecDecoding lines=1)`, `arming auto-restart`; `docker inspect RestartPolicy.Name` → `unless-stopped` ×4.
- Engram rank-offset: rank logs → layer-1 ranges `[0,96000564) [96000564,192001740) [192001740,288003654) [288003654,384006168)` on forge/anvil/ember/flame.
- Weights/KV: `Model loading took 81.58 GiB`; `GPU KV cache size: 1,374,757 tokens, Maximum concurrency for 300,000 tokens per request: 4.58x`; `/v1/models` → `max_model_len 300000`.
- Gate arithmetic: response content `"42"`, `finish=stop`, `reasoning_tokens 0` (131k and 300k boots).
- Gate JSON: `G2 parsed={'answer': 42} finish=stop`.
- Gate tool round-trip: `tool call OK: lookup_fixture {'key': 'alpha'}` + `round trip OK, content: 'The value for key **alpha** is **42**.'` + `finish: stop` (131k and 300k boots).
- Gate corrcheck: `"ok": true` with 7 PASS lines (131k: `vllm-phase3`; 300k: `vllm-300k`).
- Gate NIAH: final JSON `"ok": true`, 12/12 pass (both boots).
- Gate vision: content `"A red circle on the left and a blue square on the right."`; `usage` → `prompt_tokens 905` (image processed; `prompt_tokens_details: null`).
- Gate soak: `{"completed": 122, "failed": 0, "wall_s": 304.2}`; worker `used` before/after 121.3→121.25 / 122.7→122.8 / 122.6→122.6 GB (flat).
- Count check (300k boot): `count: 299 tok / 3.72s = 80.3 tok/s | correct 1..100: True` and `83.6 tok/s | True`.
- Bench Tony-comparable: `bench-phase3-131k.md` tables (C1 42.96/48.24 … C6 132.01; prefill 1079/811/1524/1448); drift: `bench-phase3-300k-c1.md` C1 43.04/48.71.
- Bench V4-comparable: `bench-decode-131k.log` → client_wall `median 62.84, mean 59.11, sd 10.07`; `bench-depth-131k.log` → 5k median 41.83, 10k median 42.61, `c4 aggregate_tok_s 136.71`.
- DSpark acceptance: head-log `SpecDecoding metrics` parse → v41bench window mean 4.12 (n=156); recent window p50 5.24 (min 3.10 / max 5.73).
- Telemetry: `tel-{anvil,ember,flame}.csv` → clock p10/p50/p90 2177-2190 MHz flat, power max 36-42 W.
- Final state: `docker ps` → `vllm_dsv41 Up` ×4; `curl /v1/models` → `deepseek-v4.1-flash` (max_model_len 300000).
- SGLang/qwen lanes intact: `docker image inspect local/dsv41-gb10:p2` → `sha256:47015c726232…` (the exact phase-1/2 image, untouched); `docker images local/qwen38-gb10*` → `e1`, `e1-gemv-on` present; `/home/jun/launch-dsv41-tp4.sh` mtime 2026-09-10 09:29 (pre-phase-3, unmodified, md5 4c3649157834); `/home/jun/qwen38-tuning-20260906/rollback-serve.sh` exists (head shown).

**Success-unverified items: none.** (The one cosmetic gap — forge's own bench-window telemetry CSV — is disclosed above and covered by 3/4 nodes + two idle flip probes.)
