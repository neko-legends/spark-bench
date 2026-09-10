# PREFLIGHT-CHECKLIST.md — Jun's spec → where each line is satisfied

Jun's spec (binding), from image-recipe.md, mapped line by line. "Conflict"
entries are the places where reality differs; each has a launcher lane + a
rationale — nothing was silently dropped.

## Serve topology

| Spec line | Where | Status |
|---|---|---|
| 4x GB10 as ONE endpoint | `launch-qwen38-tp4.sh`: TP=4, NNODES=4, head serves :8000 on 192.168.10.1 | ✅ |
| TP4+EP mandatory | `--tensor-parallel-size 4 --enable-expert-parallel` (hard-coded, not env-overridable) | ✅ |
| vLLM only, no TP2 pairs | vLLM day-0 image + patch stack; no SGLang anywhere | ✅ |
| CX7 RoCE, aarch64, CUDA 13 | rail B (192.168.10.0/24, MTU 9000 verified on forge); arm64 manifest `sha256:3b0e188f…`; base image torch 2.13 cu130 | ✅ |
| One NVMe copy per node, rsync fan-out over CX7 (~16 Gbps), never scp 120GB over ssh | preflight checks per-node weights at `/home/jun/models/qwen38-flash-next-nvfp4` (local NVMe; PLE table is mmapped from it — NFS is forbidden). Fan-out runbook (rsync daemon over the fabric rail, GB10 ARM AES caps ssh at ~1 Gbps) in the REPORT runbook | ✅ (runbook; forge download still running at recipe time) |
| drop_caches before loads | preflight: `sync; echo 3 \| sudo -n tee /proc/sys/vm/drop_caches` with sudo-or-skip; tsw2k's `flusher-unconditional.sh` pattern documented in the report for flaky nodes | ✅ |
| Docker nofile 1048576, ipc host, network host, gpus all | `--ulimit nofile=1048576:1048576` (tsw2k fix #2: 128 PLE mmap shards + 4-node NCCL/EP sockets overflow the default), `--ipc host`, `--network host`, `--gpus all` | ✅ |
| NCCL: no GID_INDEX; ROCE_VERSION_NUM=2 + ADDR_RANGE + HCA + SOCKET_IFNAME + GLOO | `NCCL_IB_ROCE_VERSION_NUM=2`, `NCCL_IB_ADDR_RANGE=192.168.10.0/24`, `NCCL_IB_HCA=roceP2p1s0f1`, `NCCL_SOCKET_IFNAME/GLOO_SOCKET_IFNAME/TP_SOCKET_IFNAME=enP2p1s0f1np1`, **GID_INDEX not set** (auto-detect; tsw2k caught GID index drifting 4 vs 3 after a link bounce — forge has ~250 GID indices) | ✅ |
| NCCL_CROSS_NIC=1 | `-e NCCL_CROSS_NIC=$NCCL_CROSS_NIC` default 1 (spec). Note: GLM and tsw2k both ran 0 on single-rail fabrics; spec wins, override with `NCCL_CROSS_NIC=0` if EP all2all misbehaves | ✅ |
| Quantization modelopt | model card: `--quantization modelopt` — the checkpoint carries ModelOpt quant configs (hf_quant_config.json + config.json), auto-detected; launcher does not pass `--quantization` (tsw2k/getrefined precedent). `PLE_FORCE_FP8=1` is set (image patch 0) | ✅ (auto-detect) |
| NCCL 2.30.7 host staging + LD_PRELOAD | GLM pattern: `~/nccl-2.30.7/libnccl.so.2.30.7` (verified present on forge) mounted read-only, LD_PRELOADed; staged from the glm53 donor image if missing | ✅ |

## GB10 patches (all baked into Dockerfile.qwen38-gb10, see patches/PATCHES.md)

| Spec line | Where | Status |
|---|---|---|
| PLE FP8 resolver | patch 0: getrefined `ple-force-fp8.patch` → `apply_ple_force_fp8.py` (pre-rename backport of vllm#54882/`d4d703caf`, which is NOT in the pinned image) | ✅ |
| VLLM_PLE_MMAP=1 (~48GB table on NVMe) | patch 1: `vllm_ple_mmap.py`; launcher PLE_MODE=mmap default, workers 32, prewarm 1 | ✅ |
| exact-topk/persistent_topk determinism fix | patch 5b: jschmied deterministic `persistent_topk` kernel (vllm#55122), compiled at build (`VLLM_QSA_DET_TOPK=1` default) + patch 5 exact-topk fallback (env) | ✅ |
| QSA/GDN Spark fixes | patch 2: FLA 99 KiB shmem gate + fla#953 num_warps pin (GDN); QSA determinism (above); patch 3: mamba state-copy race vllm#50729 + bounds guard; patch 4: prefix-caching block_size fix | ✅ |
| MTP loadable on the nvidia checkpoint (MiaAI merge 2026-09-05) | patch 9 (image): `FP8_BLOCK_SCALES` MTP routed experts → `Fp8MoEMethod` — the stock dispatch builds an unquantized MoE that dies ~7 min into loading; patch 11 (launcher): `patch_checkpoint_config.py` stages `mtp.layers.48` aliases for config.json + hf_quant_config.json and bind-mounts them over the container's config paths (NVMe copy untouched). MiaAI measured MTP=3 with both at TP2+EP: 2.13× decode, 72.8% acceptance | ✅ (was risk R1 — now closed) |
| fp8 KV cache | patch 10 (image): blazux `patch_qsa_fp8_kv.py`, inert at `auto`; opt-in lane `KV_CACHE_DTYPE=fp8` (~1.7× pool, quality trade) | ✅ (lane; default auto) |

## Serve flags

| Spec line | Where | Status |
|---|---|---|
| port 8000 (GLM owns 18888) | `PORT=8000`, MASTER_PORT=25100 (GLM uses 25000) | ✅ |
| served-model-name qwen3.8-flash-next | `--served-model-name qwen3.8-flash-next` | ✅ |
| EP mandatory | `--enable-expert-parallel` | ✅ |
| max-model-len 262144 | default; `VLLM_ALLOW_LONG_MAX_MODEL_LEN=0` | ✅ |
| gpu-memory-utilization 0.80 | `GPU_MEM_UTIL` default 0.80; resident lane auto-drops to 0.78; OOM fallback 0.75–0.78 via `GPU_MEM_UTIL=0.78 ./launch-qwen38-tp4.sh` | ✅ |
| MTP speculative-config (k=2) | `--speculative-config '{"method":"mtp","num_speculative_tokens":2}'` (MTP env; tsw2k measured 0.856 acceptance at k=2). **Now actually loadable on the nvidia checkpoint** via patch 9 + the launcher's config alias (MiaAI merge); the launcher preflights the MTP expert algo and fails in seconds if unbuildable | ✅ (upgraded 2026-09-05) |
| **cudagraph FULL_DECODE_ONLY sizes [1,2,4,8]** | `CUDAGRAPH_MODE=full` lane: `--compilation-config '{"mode":0,"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2,4,8]}'` | ⚠️ **CONFLICT** — see below |
| reasoning-parser qwen3, tool-call-parser qwen3_coder | both + `--enable-auto-tool-choice` | ✅ |
| max-num-seqs 16, mnbt 8192, chunked prefill, prefix caching | all four, tsw2k defaults | ✅ |
| mm-encoder-tp-mode data (MiaAI merge) | `--mm-encoder-tp-mode data` — vision MLP intermediate 4304 is not %16 after TP split (2152@TP2, 1076@TP4); MiaAI-verified on this checkpoint+image | ✅ (new 2026-09-05) |
| kv-cache-dtype | default `auto` (bf16, tsw2k-proven); opt-in `KV_CACHE_DTYPE=fp8` lane via image patch 10 (~1.7× pool; quality trade on sparse attention — validate before trusting) | ✅ |
| moe-backend marlin (FlashInfer CUTLASS Xid 31 on sm121) | `MOE_BACKEND=marlin` default → `--moe-backend marlin` | ⚠️ unverified on day-0 image (see report risk R3) |
| 1M YaRN NOT default | not set; YaRN lane documented (tsw2k: 1M lane hits the vllm#54629 deep-prefill wall) | ✅ |
| Boot order workers then head | rank 3→2→1 with 15 s gaps, then head | ✅ |
| Pin image digest on all 4 nodes | base image digest-pinned in Dockerfile; preflight verifies the BUILT image's `docker image inspect .Id` is identical on all ranks (GLM/tsw2k lesson: ID, not tag) | ✅ |

## Environment

| Spec line | Where | Status |
|---|---|---|
| PLE mmap workers 32, prewarm | `VLLM_PLE_MMAP_WORKERS=32`, `VLLM_PLE_MMAP_PREWARM=1` | ✅ |
| FP8 checkpoint | `nvidia/Qwen3.8-Flash-Next-NVFP4` (downloading on forge); PLE + MTP experts in FP8 (`model-fp8-mtp-ple.safetensors`, 53.7 GB) — PLE_FORCE_FP8=1 env | ✅ |
| TORCH_CUDA_ARCH_LIST=12.1f | `-e TORCH_CUDA_ARCH_LIST=12.1f` | ✅ |
| CUTE_DSL_ARCH=sm_121a | `-e CUTE_DSL_ARCH=sm_121a` | ✅ |
| FLASHINFER_CUDA_ARCH_LIST=12.1a | `-e FLASHINFER_CUDA_ARCH_LIST=12.1a` | ✅ |
| NCCL_CROSS_NIC=1 | default 1 | ✅ |

## OOM fallback / ops

| Spec line | Where | Status |
|---|---|---|
| OOM fallback gpu-mem 0.75-0.78 or PIECEWISE with PLE/QSA/GDN splitting ops | `GPU_MEM_UTIL=0.78` override; PIECEWISE lane carries the full splitting-op list (blazux's, verbatim) | ✅ |

## Success bar (what to measure at boot — see report §validation)

`/v1/models` 200 · temp-0 3× byte-identical · NIAH 4k/32k/128k · tool call round-trip ·
single-stream ≥28 (target 31; tsw2k measured 31.0) · aggregate ≥90@8 / stretch 157@16
(tsw2k: 97.0@8, 157.0@16) · MTP accept ≥0.80 (tsw2k: 0.856) · KV pool ~millions
(tsw2k: 5,211,726 tokens bf16 @ 0.80). tsw2k's `evals/gate_suite.py` (G1–G5)
implements almost exactly this list — clone the repo at `497a58e` and run it against
`http://192.168.10.1:8000`.

---

## CONFLICT: cudagraph FULL_DECODE_ONLY vs VLLM_PLE_MMAP=1 (spec self-conflict)

Jun's spec requires BOTH `VLLM_PLE_MMAP=1` AND `cudagraph FULL_DECODE_ONLY sizes [1,2,4,8]`.
On this stack those two cannot coexist:

- The mmap PLE gather is **CPU work + a pageable host→device copy** wrapped in the
  `vllm::ple_mmap_lookup` custom op. A CUDA graph capture that includes it dies with
  *"Cannot copy between CPU and CUDA tensors during CUDA graph capture"*. blazux's
  HOW-IT-WORKS is explicit: PIECEWISE + splitting ops ("never FULL*"), or eager
  (and eager does not fully suppress capture here).
- The FULL_DECODE_ONLY + capture-sizes shape is getrefined's — a **resident-PLE** lane
  (no mmap; table vocab-sharded on GPU, ~12 GiB/rank at TP4, boots at 0.78).

Launcher resolution (no requirement dropped — both lanes exist):

| Lane | Env | PLE | cudagraph | Proven by |
|---|---|---|---|---|
| **Default** | `CUDAGRAPH_MODE=piecewise` (default) | mmap (spec) | PIECEWISE + splitting ops | tsw2k quad fleet (passes its full gate suite) |
| Spec-lane | `CUDAGRAPH_MODE=full PLE_MODE=resident` | resident | FULL_DECODE_ONLY, sizes [1,2,4,8] | getrefined dual-Spark (TP2+EP, MTP3); MiaAI also runs FULL_DECODE_ONLY + resident PLE (sizes 1–64) on the nvidia checkpoint at TP2 — same shape |

The launcher **refuses** `full`+`mmap` (known capture death) unless `FORCE_FULL_MMAP=1`.
Recommended first boot: the default (piecewise+mmap); measure; then A/B the
full+resident lane for decode headroom if the KV pool cost (~12 GiB/rank) is acceptable.

## MiaAI merge notes (2026-09-05)

- **YaRN overrides must nest under `text_config`** (MiaAI discovery): vLLM's
  `ModelConfig._apply_dict_overrides` only recurses into keys that are nested
  configs; a top-level `rope_parameters` override is setattr'd onto the parent
  and never reaches `text_config` — every earlier "1M context" run in their repo
  served 1M positions on *unscaled* rope. If the YaRN lane is ever exercised,
  the override must be `--hf-overrides '{"text_config":{"rope_parameters":{...}}}'`.
  (Our default lane is native 262144, no YaRN — unaffected.)
- **EP stays mandatory**: MiaAI also runs EP ("required for NVFP4") at TP2; they
  do not demonstrate NVFP4 TP loading without it.
- **MiaAI divergences adopted**: `--mm-encoder-tp-mode data`, `--cap-add SYS_NICE`,
  the MTP algo fast-fail preflight, the checkpoint-config alias pattern.
- **MiaAI divergences rejected**: hardcoded `NCCL_IB_GID_INDEX=3` (tsw2k GID-drift
  lesson; auto-detect stays), NFS weight sharing (spec forbids NFS for the PLE
  mmap lane), TP2-shaped defaults (GMU 0.835 / MTP=3 / MAX_NUM_SEQS=8 — ours stay
  tsw2k TP4), `--safetensors-load-strategy lazy` (documented as an EXTRA_ARGS
  option, not default), reduced-vocabulary MTP drafting (measured acceptance
  trade), QSA gb10 profiles (unbenchmarked starting point), FP8-dense checkpoint
  (we serve the official checkpoint as published).
- Full adopt/reject rationale and evidence: image-recipe.REPORT.md § "MiaAI merge".

## Watchdogs to coordinate with (do not modify — plan around)

- **glm-cluster-watch.service** (user unit, THIS eva-core box, active): watches GLM on
  forge/anvil/ember/flame, OOM-storm early warning, and **auto-RELAUNCHES GLM** when it
  looks dead. It will fight a Qwen38 deployment on the same nodes: before any Qwen38
  boot, Jun/Depths must stop/park it (`systemctl --user stop glm-cluster-watch.service`
  — deliberately not done by this recipe) or it will re-launch GLM onto nodes Qwen38
  needs. The launcher's preflight also refuses to boot next to a live GLM container.
- **spark-forge-watchdog.timer** (user unit, eva-core box, currently *inactive*): detects
  + auto-recovers the GLM quad-spark server every 2 min. Same coordination needed if
  re-enabled.
- GLM itself is **live on forge right now** (container `glm53-exl3`, port 18888) and the
  Qwen38 download is the only allowed active job — nothing on the sparks was touched.
