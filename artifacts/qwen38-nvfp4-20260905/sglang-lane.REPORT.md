status: success

# sglang-lane.REPORT.md — SGLang feasibility for Qwen3.8-Flash-Next-NVFP4 on 4x DGX Spark

Research + preparation only, per the lane constraints. **No cluster writes, no
docker builds/launches, no installs, no commits.** The only cluster interaction
was read-only ssh to forge (docker images / docker inspect / docker ps /
nvidia-smi query). The live vLLM TP4 serve was never touched — verified running
before and after (note: `qwen38-nvfp4` showed "Up 39 min" at first check and
"Up 6 min" at last check; the restart was external to this lane — this session
issued no mutating command on any node). All web fetches were read-only
(GitHub API/raw, HF, Docker Hub registry + hub API, docs.sglang.io,
staging.lmsys.org).

## Verdict

**needs-patches-listed (viable at TP2-pairs only; TP4-on-4-nodes is hard-blocked
on GB10 by an upstream kernel contract).**

- SGLang has **day-0 support** for the qwen4_exp architecture (GDN+QSA hybrid,
  GR/HyperConnection, PLE n-gram embedding, IndexShare MTP/NEXTN) — released
  2026-08-26 with the model, by the SGLang team at **RadixArk** with Qwen/NVIDIA/
  AMD (lmsys.org blog 2026-08-26, PR #36497/#36585 lineage, cookbook page).
- On **GB10/SM121** the current image (`lmsysorg/sglang:qwen38flashnext`,
  rebuilt **2026-09-03**) finally has a working QSA decode path — but the
  purpose-built SM121 kernel is **contract-limited to TP1 (24Q/2KV) and TP2
  (12Q/1KV)**. At TP4 each rank would run 6Q/1KV → `ValueError: unsupported
  SM121 QSA call` (verified in source). TP4 across our 4 nodes is impossible on
  this image without writing a new kernel.
- The **official nvidia checkpoint** (mixed ModelOpt: NVFP4 main + FP8 PLE +
  FP8_BLOCK_SCALES MTP) is *almost* supported by the 2026-09-03 image: a
  dedicated 128-shard PLE loader with **FP8 auto-switch** landed for exactly
  this layout, and `MIXED_PRECISION` + `quantized_layers` routes to
  `modelopt_mixed`. The **one remaining gap is MTP**: no `FP8_BLOCK_SCALES`
  branch anywhere in sglang's ModelOpt dispatch (verified by grep) → NEXTN on
  the nvidia checkpoint needs a small patch (the SGLang twin of our vLLM patch
  9), or must run with spec decoding off.
- The lane's assumed local donor image `glm53-sglang-sm121:dflash` **does not
  exist** — see "Premise corrections".

**Lane shape:** 2 × TP2 endpoints (forge+anvil, ember+flame), optionally fronted
by `sgl-router` (cache_aware). Expected per-stream decode ~37–47 tok/s (better
than our vLLM TP4 SS 26.3), aggregate ~300 tok/s @16 across both endpoints
(slightly below vLLM TP4's 344). Honest recommendation at the end.

## Task 1 findings (the SGLang path for this exact checkpoint)

### 1a. Does SGLang support the architecture? — Yes, day-0, officially

- **LMSYS day-0 blog** (staging.lmsys.org/blog/2026-08-26-qwen-flash-next,
  fetched in full): Qwen3.8-Flash-Next support shipped 2026-08-26 with the
  model, by "the SGLang team at RadixArk" + Qwen + NVIDIA + AMD. All four
  exotic components are implemented:
  - **GDN + QSA hybrid**: 36 GDN linear-attention + 12 QSA sparse-attention
    layers; QSA indexer (4×128-d query heads, 1 shared key head, c4 compression,
    512-block budget / 2048 logical positions — matches our checkpoint's
    `indexer_budget` 2048, `compress_ratio` 4); KV-cache management compatible
    with Radix Cache; page-aligned `full_slot/4` compressed addressing.
  - **GR/HyperConnection**: Mix/Combine via FlashInfer PR #4266 split-K CuTe
    GEMMs (2.05×/1.96× kernel speedups, +7.6%/+5.5% end-to-end on B300).
  - **PLE n-gram embedding**: 51.2B params, 16 hash rows/token × 160 dims;
    **pinned-host offload** with async prefetch (−23.46 GiB/GPU, +78.5% KV on
    H200 TP4, −0.07% throughput, bit-identical outputs). "Enabled by default
    when the effective model dtype is BF16" — for NVFP4 checkpoints the table
    stays in weights (see §1d).
  - **IndexShare MTP**: draft decode skips the QSA indexer (draft-extend
    selection frozen for the whole MTP iteration); B200 TP4 NVFP4 = 540 tok/s
    bs1, accept length 3.3.
- **SGLang cookbook** (docs.sglang.io cookbook Qwen3.8-Flash-Next, fetched):
  "Qwen3.8-Flash-Next support is not in a tagged release yet" — day-0 branch /
  `qwen38flashnext` image. Verified matrix: H200/B200/B300/GB300 only;
  NVFP4 = RadixArk re-quant, **"Blackwell only"** — GB10/SM121 is NOT in the
  signed-off matrix. Community recipes closed that gap (see §1b/§1c).
- **Support PRs/issues**: qwen4_exp model support PR #36585; the working branch
  is `qwen4-main-squashed` (base 73a2552 for the Aug-26 images; the Sep-3 image
  is built from commit **593134d17a6eb0d0fc5f71a970cd2e9dc8e26e8b**, verified
  via image labels, see §2).

### 1b. What image?

**Recommended: `lmsysorg/sglang:qwen38flashnext` @
`sha256:5ae5816783d58e2e56e84d2e863f5441425056f500b7fbd7448c4aae017a2521`**
(multi-arch; **arm64 manifest
`sha256:c93d57460ce7fca986c7c8150b5a2231b540ca226d17ef5563ac0dcee506c136`**,
config blob `sha256:f52b4afd…`, 15.0 GB). Verified via Docker Hub registry +
hub APIs:

- Tag **re-pushed 2026-09-03T20:54Z** (same digest for `dev-qwen38flashnext`
  and `dev-cu13-qwen38flashnext`; `dev-cu12-qwen38flashnext` is a separate
  cu12 build, digest 55fa0f28…). **Pin by digest** — this tag has already been
  re-cut once (the 2026-08-26 digests `sha256:64c58f100438` and `sha256:12d3392b…`
  cited in issues #36558/#37326 are gone).
- Image labels (arm64 config blob): `ai.sglang.build.commit =
  593134d17a6eb0d0fc5f71a970cd2e9dc8e26e8b` (dated 2026-09-03, "upd"), built by
  GitHub Actions run 33744460271. Environment from issue #37326's sibling image:
  torch 2.13.0+cu130, CUDA 13.0, sglang-kernel 0.4.6.post1, flashinfer 0.6.17,
  triton 3.7.1, transformers 5.12.1, arm64.
- **What the Sep-3 rebuild fixed (verified in the source at 593134d1):**
  1. **SM121 QSA decode** — new `python/sglang/kernels/kda_kernels/qwen38_qsa_sm121/`
     package: a KDA-1.5-competition winning packed-varlen decode kernel
     specialized for *this exact model's* QSA decode tensors on GB10 (BF16,
     D=256, TP1 24Q/2KV / TP2 12Q/1KV, bs≤128, selected-KV≤2055). Validated
     15/15 production-tensor replay on two GB10s, 150k consecutive launches,
     2.07× geomean over the generic Triton fallback, +4.45% e2e at c1 on one
     Spark with NEXTN, GSM8K 49/50 (kernel README, fetched).
  2. **nvidia-checkpoint PLE shard loader** — `load_qwen4_exp_ple_shard()` in
     `python/sglang/srt/models/qwen4_exp.py` recognizes
     `.ngram_embedding.shard_N.weight` tensors (the nvidia 128-shard layout,
     [2500012,160] F8_E4M3 × 128) and **auto-switches embedding storage to FP8**
     when the shards are F8_E4M3. This is the SGLang twin of vLLM #54882 / our
     patch 0 — already upstream in the Sep-3 image. Caveat: if PLE pinned-host
     offload is engaged, the auto-switch refuses and requires
     `text_config.ple_embedding_dtype="float8_e4m3fn"` (error message in source).
  3. **MIXED_PRECISION routing** — `ModelConfig._parse_modelopt_quant_config`
     maps `quant_algo == "MIXED_PRECISION"` + NVFP4 entries in `quantized_layers`
     → `modelopt_mixed`. Verified the nvidia `hf_quant_config.json` parses into
     this path (50 entries: NVFP4×48, FP8×1 [PLE], FP8_BLOCK_SCALES×1 [MTP]).
- **Do NOT use the Aug-26 digests / community forks of it**: they crash on
  SM121 (issue #36558: FA4 CuTe `MLIRError` at decode/capture; pocharlies needed
  FA2-ABI stub + trtllm-gate hot patches). Also **do not use pocharlies'
  baked-patch image**: it widens the trtllm sparse-decode gate to SM121 — the
  exact approach upstream **rejected** (PR #36566 closed unmerged 2026-08-26,
  CI failed) because, per the in-code comment at 593134d1: *"This path is
  numerically validated on SM100 and SM120. Do not widen it to every SM12x
  device: it silently corrupts long-context decode on SM121/GB10."*
- aarch64 pip route: still a dead end (sgl-kernel wheel ABI, our 2026-08-20
  note stands). Use the docker image.

### 1c. Required patches for GB10/sm_121 — what's left after the Sep-3 image

| # | Gap | Status in `qwen38flashnext@5ae58167` (commit 593134d1) | Patch needed? |
|---|---|---|---|
| A | QSA decode kernel on SM121 | **Fixed upstream (Sep-3)**: dedicated KDA `qwen38_qsa_sm121` kernel; trtllm path deliberately refused on SM121 | None — but **TP≤2 only** (see §1e) |
| B | NVFP4 ModelOpt mixed config | `modelopt_mixed` routes nvidia's MIXED_PRECISION + quantized_layers | None (do NOT pass `--quantization modelopt_fp4`: `common_group_size` raises on the 16-vs-128 group_size inconsistency — auto-detect instead) |
| C | PLE FP8 (nvidia 128-shard layout) | **Fixed upstream (Sep-3)**: shard loader + fp8 auto-switch | None on the weights path. Only if using PLE pinned-host offload: config overlay `text_config.ple_embedding_dtype="float8_e4m3fn"` (RadixArk declares exactly this; pocharlies-verified fp8-on-disk→fp8-in-pool on sm_121a) |
| D | **MTP draft experts = FP8_BLOCK_SCALES (128×128 block-scaled FP8)** | **GAP**: no `FP8_BLOCK_SCALES` branch anywhere in `modelopt_quant.py`'s `ModelOptMixedPrecisionConfig.get_quant_method` (verified by grep; dispatch handles only FP8 / FP8_PB_WO / MXFP8 / NVFP4 / W4A16_NVFP4). The nvidia checkpoint does NOT put `mtp.*` in exclude_modules (verified in both config files) → draft MoE builds unquantized → dies at weight load (missing scale params), the same failure class our vLLM patch 9 fixed | **Yes, for NEXTN**: either (i) port the patch-9 concept to sglang (route `FP8_BLOCK_SCALES` + checkpoint `group_size` 128 → SGLang's own blockwise Fp8 MoE method, `weight_block_size=[128,128]`; small, self-contained, same file, `get_quant_method`), or (ii) run `ENABLE_MTP=false` (no spec decode — ~2.3× SS cost, from pocharlies' accept-length 2.3) |
| E | MTP/mamba **uptime decay** | **GAP (bug #37326, still open, updated 2026-09-04)**: NEXTN draft acceptance decays to ~0 over ~24h (ghost mamba radix-cache nodes); PR #35821's `torch.minimum` clamp is **absent** at both `spec_utils.py` sites in the Sep-3 image (verified in source at 593134d1: lines ~848 and ~1020 both unbounded `torch.clamp`) | Ops mitigation (probe `sglang:spec_accept_length` every 6h, coordinated restart below 0.35) or cherry-pick `23e51dd`/#35821 + the second clamp site into the image |
| F | Thinking-off control | Model "always reasons"; `enable_thinking:false` via `chat_template_kwargs` works (pocharlies, production-verified; note SGLang splits into `reasoning_content` — same field vLLM's day-0 build did NOT use, it used `message.reasoning`) | None — but the bench harness must pass it (see §4) |

**Premise corrections (things the lane brief got wrong):**

- **`local glm53-sglang-sm121:dflash` does not exist.** Read-only `docker images`
  on all four nodes (forge/anvil/ember/flame) shows exactly: `local/qwen38-gb10:e1`,
  `local/glm53-exl3:e2`, `ghcr.io/miaai-lab/glm-5.3-flash-2x-dgx-sparks:exl3`,
  `dspark-vllm-gx10:0.1.1-flashinfer-0.6.15`, alpine/socat, alpine. The NCCL
  donor is `local/glm53-exl3:e2` — a **vLLM-based** image (labels:
  `ai.vllm.build.*`, VLLM_* env, exllamav3 overlay per `docker history`), not
  sglang. The last SGLang image we had, `lmsysorg/sglang:dev-cu13-inkling-dspark`
  (2026-08-20 DSpark attempt), is gone from all nodes. No usable local sglang
  donor exists; NCCL 2.30.7 staging for an SGLang lane must come from the same
  pip-donor path (via `local/glm53-exl3:e2`, which contains pip nvidia-nccl-cu13
  2.30.7 per our launcher's staging logic) or be re-derived.
- **"MiaAI's repo has an SM121 QSA gate patch note for SGLang"** — conflated.
  MiaAI-Lab's public Qwen3.8 repo is **vLLM-only**; their GHCR images are
  vLLM/Ray (glm53-flash-spark:mm-ray-v1) or exllamav3. The SM121 QSA gate
  lineage is **ursuciprian** (issue #36558, PR #36566 — gate widening, rejected
  upstream) and **pocharlies** (baked the same gate patch, now superseded by the
  upstream KDA kernel). There IS a community `0xSero/glm-5.3-flash-sglang-sm121`
  Dockerfile and a `lmsysorg/sglang:glm-5.3-flash` official tag — neither is on
  our nodes.

### 1d. NVFP4/ModelOpt support specifics (our exact checkpoint)

Verified against the nvidia checkpoint's real `config.json` +
`hf_quant_config.json` (fetched from HF) and sglang source at 593134d1:

- Routing: `quant_method: "modelopt"` + `quant_algo: "MIXED_PRECISION"` +
  `quantized_layers` (50 entries incl. NVFP4) → `modelopt_mixed`. ✓
- Main experts NVFP4 → `ModelOptNvFp4FusedMoEMethod` (flashinfer cutlass /
  trtllm / cutedsl / marlin backends; pocharlies ran flashinfer cutlass NVFP4
  on sm_121a at TP2). ✓
- PLE → nvidia 128-shard loader + fp8 auto-switch (§1c-C). Empirically the
  sibling RadixArk layout (also FP8-on-disk PLE, ~74 GiB/rank weights at TP2
  incl. the table, "avail mem ~33–35 GB" after load at 0.90 — pocharlies,
  measured on sm_121a). Our nvidia checkpoint is the same size class
  (132.7 GB total, PLE ≈48 GB fp8). ✓
- MTP → FP8_BLOCK_SCALES gap (§1c-D). ✗ until patched.
- Vision tower: nvidia ignore list leaves `model.visual.*` unquantized (BF16)
  — same as RadixArk; pocharlies served vision on the same path. ✓ (our vLLM
  lane additionally needed `--mm-encoder-tp-mode data` for TP4; at TP2 the
  vision MLP 4304/2=2152 is still not %16 — pocharlies ran it at TP2 without
  noting a crash, so unverified either way; flag for first boot.)

### 1e. Multi-node: TP4? EP? — the decisive constraint

- **Mechanics are fine**: SGLang multi-node TP is `--tp N --nnodes N
  --node-rank R --dist-init-addr host:port` (+ `MASTER_ADDR/PORT`, `--gpus all`,
  rail-B NCCL env). We proved rendezvous on this exact fabric on 2026-08-20
  (DSpark TP4, all 4 nodes; gotchas documented: `dist-init-addr` must be a bare
  `host:port` — `NetworkAddress.parse` does not strip `tcp://`; per-node GID
  auto; `--ulimit memlock=-1`). Pocharlies runs 2-node TP2 over RoCEv2 in
  production. The preserved shape is `scripts/launch-sglang-tp4.sh`.
- **TP4 for qwen4_exp on GB10 is blocked by the QSA decode kernel**: at TP4
  each rank has 6 query heads / 1 KV head; the only SM121 decode kernel
  rejects it (`_SUPPORTED_HEAD_TOPOLOGIES = {(12,1), (24,2)}` in
  `kernels/kda_kernels/qwen38_qsa_sm121/__init__.py`, and
  `qwen38_qsa_sm121_varlen` **raises** on any other shape). The trtllm
  alternative is explicitly refused on SM121 (silent long-context corruption,
  §1b). A TP4 lane would require writing/extending an SM121 packed-varlen QSA
  kernel for 6Q/1KV — real kernel work, not a config patch. Also note even
  upstream's verified matrix stops at B200/GB300; nothing published runs this
  model at TP>2 on GB10.
- **EP doesn't help**: SGLang expert parallelism (`--enable-ep-moe` /
  moe-a2a backends) shards experts, but the per-rank QSA head count is set by
  tensor-parallel size regardless. (For completeness: at TP2 nobody needs EP —
  pocharlies runs plain TP2 with intermediate 320/rank, no EP flags.)
- **DP-attention** (`--enable-dp-attention`, full heads per rank on a request
  subset) would nominally keep 24Q/2KV per rank and dodge the kernel limit,
  and the qwen4_exp model has dp-awareness code (`gather_dp_tokens` in the PLE
  module), but DP-attention + hybrid GDN state + 4-node + this image is
  completely unverified territory — do not plan the first bench on it.
- **Realistic lane shape (documented per the task): TP2 pairs.** Two
  independent TP2 endpoints (forge+anvil, ember+flame), each the
  community-proven shape. Optionally front both with
  `python -m sglang_router.launch_router --worker-urls http://A:PORT
  http://B:PORT --policy cache_aware` (sgl-router is the documented pattern for
  fronting multiple TP groups; preserves prefix-cache locality). Alternatively
  keep routing in eva-core's layer. A single TP2 endpoint (2 nodes idle) is the
  minimal first bench.

## Task 2 — Launch command sketch (recommended topology: 2× TP2)

Nothing below was executed; it is the operator-ready shape, adapted from our
proven `scripts/launch-sglang-tp4.sh` (fabric env, proven 2026-08-20) +
pocharlies' production-verified GB10 TP2 parameters + #37326's args.

Per pair (e.g. pair A = forge rank0 + anvil rank1), run on each node:

```bash
docker run -d --name sglang-qwen38-tp2 --restart no \
  --network host --ipc host --gpus all --shm-size 64g \
  --device /dev/infiniband \
  --ulimit memlock=-1 --ulimit stack=67108864 \
  --memory 112g \
  -v /home/jun/models/qwen38-flash-next-nvfp4:/models/qwen38:ro \
  -e NCCL_NET=IB -e NCCL_IB_DISABLE=0 -e NCCL_NVLS_ENABLE=0 \
  -e NCCL_IB_GID_INDEX=auto -e NCCL_IB_ROCE_VERSION_NUM=2 \
  -e NCCL_IB_ADDR_FAMILY=AF_INET -e NCCL_IB_ADDR_RANGE=192.168.10.0/24 \
  -e NCCL_IB_HCA=roceP2p1s0f1 -e NCCL_SOCKET_IFNAME=enP2p1s0f1np1 \
  -e GLOO_SOCKET_IFNAME=enP2p1s0f1np1 -e TP_SOCKET_IFNAME=enP2p1s0f1np1 \
  -e NCCL_CUMEM_ENABLE=0 -e NCCL_IGNORE_CPU_AFFINITY=1 -e NCCL_DEBUG=WARN \
  -e MASTER_ADDR=192.168.10.1 -e MASTER_PORT=26000 \
  -e MAX_JOBS=1 -e TORCHINDUCTOR_COMPILE_THREADS=4 \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  lmsysorg/sglang:qwen38flashnext@sha256:5ae5816783d58e2e56e84d2e863f5441425056f500b7fbd7448c4aae017a2521 \
  python3 -m sglang.launch_server \
    --model-path /models/qwen38 \
    --served-model-name qwen3.8-flash-next \
    --host 0.0.0.0 --port 30000 \
    --tp 2 --nnodes 2 --node-rank ${RANK} \
    --dist-init-addr 192.168.10.1:26000 --dist-timeout 3600 \
    --context-length 262144 \
    --mem-fraction-static 0.90 \
    --page-size 64 \
    --mamba-scheduler-strategy extra_buffer --mamba-track-interval 64 \
    --chunked-prefill-size 2048 \
    --max-running-requests 8 \
    --speculative-algorithm NEXTN \
      --speculative-num-steps 3 --speculative-eagle-topk 1 \
      --speculative-num-draft-tokens 4 \
    --reasoning-parser qwen3 --tool-call-parser qwen3_coder \
    --enable-metrics --watchdog-timeout 600 \
    --disable-flashinfer-autotune   # FIRST boot only (JIT-cache cold); re-enable after
```

Notes (all sourced, see §1c table):
- `--dist-init-addr` = **bare host:port** (no `tcp://` scheme — 2026-08-20 lesson).
- `MAX_JOBS=1` is **mandatory on GB10**: one flashinfer FP4 `cicc` peaks at
  7.7 GB RSS; ninja's default parallelism global-OOMs the node during first
  CUDA-graph capture (pocharlies, measured). `TORCHINDUCTOR_COMPILE_THREADS=4`
  for the same reason. JIT cache persists — later boots are clean.
- `--page-size 64`, mamba `extra_buffer` + track-interval 64: mandatory for
  radix cache over the hybrid GDN state (pocharlies + #37326 production args).
- `--mem-fraction-static`: pocharlies shipping 0.90 (KV ~1.37M tok @8cc);
  alternates measured 0.78 (365K), 0.85/0.86 (1.02M/737K); 0.94 = the edge
  (hangs autotune, not recommended). On GB10 the GPU pool IS system memory —
  the OOM that matters is the **global node** one.
- `--speculative-num-draft-tokens 4`: the compress-ratio guard rejects >4 on
  this model (#36558 reporter, measured).
- Ports: keep clear of vLLM :8000 (forge) and GLM's 18888; use 30000/30001 per
  endpoint + router on 30200. MASTER_PORT/dist ports per pair (26000/26100) —
  never GLM's 25000.
- Second pair (ember+flame): same shape, `--dist-init-addr 192.168.10.3:26100`,
  port 30001, MASTER_ADDR=192.168.10.3.
- Optional front: `python -m sglang_router.launch_router --host 0.0.0.0
  --port 30200 --worker-urls http://192.168.10.1:30000
  http://192.168.10.3:30001 --policy cache_aware`.
- **First-boot probes** (before trusting any number): boot log
  `max_total_num_tokens` (must be ≥ 262144 — one intermediate config silently
  left it at 67K, pocharlies); PLE auto-switch line ("PLE embedding switched
  to fp8 storage"); `avail mem` after load (~33–35 GB at 0.90); MTP draft
  graphs captured. If patch D (FP8_BLOCK_SCALES) is not applied, drop the four
  `--speculative-*` flags.
- **Restarts are coordinated per pair** (a rank that restarts alone waits 601 s
  for TCPStore rendezvous then dies — pocharlies).
- Thinking-off for benchmark parity: every request carries
  `"chat_template_kwargs": {"enable_thinking": false}`.

## Expected tok/s (honest, precisely sourced)

All community numbers are on the **RadixArk re-quant** (experts-only NVFP4,
BF16 MTP/PLE-fp8 layout) on **2× DGX Spark TP2**; nobody has published numbers
on the official nvidia checkpoint or >TP2 on GB10.

| Source (all 2× Spark TP2, SGLang) | Config | Numbers |
|---|---|---|
| pocharlies (HF model card, prod-verified 2026-08-27, 30-min soak) | RadixArk NVFP4, NEXTN 3/1/4 (accept ~2.3), 0.90, 8cc | **SS 41–42 tok/s; 153 tok/s agg @8** (139–166, no degradation); prefill 2.5K tok/s cold 72K single, 7.7–11.8K tok/s agg large-context; 0.5 s 30K-prefix re-serve (radix) |
| ursuciprian (issue #36558, interim Triton fallback, llama-benchy pp2048/tg128) | RadixArk NVFP4, TP2, MTP steps3/draft4 | c1 no-spec 24.6; **c1 MTP 37.6**; c2 MTP 49.2 (flat to 16k depth; c1 is cuBLAS-gemv-bound on GB10, 52% of GPU time) |
| #37326 reporter (production, RadixArk) | NEXTN 3/1/4, TP2 | fresh-boot SS 31–47 (74.5 peak single logged decode batch); after 4 days: 16.4–19.6 (the decay bug) |
| hasso5703 (single Spark, NVMe-mmap PLE overlay) | NEXTN, TP1 | 34–42 tok/s decode; prefill 1.5–2K tok/s |
| The lane brief's "RadixArk 40–100 t/s" | — | maps to: typical SS 37–47, peaks 70–75; nothing sustained near 100 on 2 Sparks |

**Projection for our 2× TP2 lane (same hardware class, nvidia checkpoint):**
SS ~35–45 tok/s per endpoint (thinking-off must be re-measured — community
numbers are not guaranteed thinking-off), aggregate ~150 tok/s @8 per endpoint
→ **~300 tok/s @16 across both endpoints**. Versus our vLLM TP4 (SS 26.3,
agg 105.5@4 / 210.6@8 / 344.0@16, MTP accept 0.944, KV pool 5.06M):

- **Per-stream**: SGLang TP2-pair likely **wins** (~1.5× vs 26.3) — fewer
  ranks per token, deeper spec (accept 2.3 vs 1.9-equiv).
- **Aggregate ceiling**: vLLM TP4 likely **wins** (~344 vs ~300 @16).
- **KV capacity**: vLLM TP4 wins (5.06M vs ~2×1.37M ≈ 2.74M total).
- At equal TP2, note vLLM (MiaAI, MTP3) measured 52.1 tok/s batch-1 vs SGLang
  ~41–42 — vLLM is faster *at TP2*; SGLang's lane appeal is the TP2-pair shape
  (per-stream latency) + radix cache + prefix locality, not raw engine speed.

**Honest recommendation:** the SGLang lane is worth benching **only if** (a)
per-stream latency matters more than aggregate (agent/eva-core workloads at
low concurrency), or (b) Jun wants the 2-endpoint redundancy. For pure
aggregate throughput on the quad, vLLM TP4 stays the better shape. If benched:
apply patch D (FP8_BLOCK_SCALES) first — without MTP the SGLang lane forfeits
its per-stream advantage (~24 tok/s no-spec, per #36558's c1 measurement).

## Task 3 — Risks

- **R-S1 (blocker): TP4 impossible on GB10** — SM121 QSA decode kernel
  contract {(12,1),(24,2)}; TP>2 raises at first decode. Any 4-node SGLang plan
  requires new kernel work (6Q/1KV packed-varlen) — not a config fix.
- **R-S2: MTP on the nvidia checkpoint needs the FP8_BLOCK_SCALES dispatch
  patch** (§1c-D). Unverified at runtime (no boot allowed) — the mechanism is
  source-verified (no branch in `ModelOptMixedPrecisionConfig.get_quant_method`;
  nvidia excludes nothing under `mtp.*`). Fallback: spec off.
- **R-S3: uptime decay (#37326, open)** — NEXTN acceptance → 0 over ~24h from
  mamba radix ghost nodes; the Sep-3 image lacks both `torch.minimum` clamps
  (source-verified). Any long-running SGLang+NEXTN deployment needs the
  accept-rate probe + coordinated restart cycle (~9–10 min/pair), or a patched
  image carrying `23e51dd` + the second clamp site.
- **R-S4: mutable tag** — `qwen38flashnext` was re-cut once already (Aug-26 →
  Sep-3 digests differ). Pin by digest `5ae58167…`; re-verify labels
  (`ai.sglang.build.commit=593134d1`) after any re-pull.
- **R-S5: day-0, unreleased code** — "not in a tagged release yet" (cookbook);
  dev build from a squashed branch; GB10/SM121 entirely outside the verified
  matrix. Community validation is 2-node TP2 on a *different* checkpoint
  layout (RadixArk). Expect first-boot surprises; budget boots, not minutes.
- **R-S6: trtllm-gate temptation** — pocharlies/PR#36566-style gate-widening
  boots TP4-shaped workarounds but "silently corrupts long-context decode on
  SM121" per upstream comment. Do not adopt.
- **R-S7: memory edges** — MAX_JOBS=1 mandatory (JIT OOM), mem-fraction 0.90 is
  the shipping edge (0.94 hangs autotune); the GB10 OOM that matters is global
  node OOM, not cgroup.
- **R-S8: no local sglang image / NCCL donor premise wrong** —
  `glm53-sglang-sm121:dflash` doesn't exist; NCCL 2.30.7 staging must reuse the
  pip donor (`local/glm53-exl3:e2`) or a fresh pull. Also SGLang serves its own
  NCCL 2.30.x from the image — our host-staged-LD_PRELOAD override was needed
  for vLLM on this fabric; whether SGLang's bundled NCCL works on rail B is
  untested here (our 2026-08-20 SGLang boots worked with the same env family).
- **R-S9: co-exidency** — a TP2 pair needs the full 128 GB pool of its two
  nodes; the vLLM TP4 lane owns all four right now. The two lanes cannot share
  the quad; benching SGLang means tearing down vLLM (Jun's call).

## What to measure for a fair comparison vs our vLLM numbers

Same harness, same contract, exactly as `results/qwen38-nvfp4-tp4-2026-09-05.json`:

1. **Usage-verified tokens**: completion tokens from response `usage` ÷
   end-to-end wall (same field both engines). Temp 0.
2. **Thinking off on both**: vLLM lane ran thinking-off; SGLang requests must
   carry `chat_template_kwargs {"enable_thinking": false}` (pocharlies-verified;
   the model always thinks otherwise).
3. **Same corpus**: 1200-token code streams, nonce-suffixed prompts, same
   concurrency ladder (1/4/8/16). For the 2-endpoint lane, split load across
   both endpoints (8 per endpoint at 16) — via sgl-router or the harness.
4. **Spec parity note**: vLLM MTP k=2 (accept 0.944) vs SGLang NEXTN 3/1/4
   (accept ~2.3) — different spec depths; report acceptance alongside so the
   comparison is decomposable (`sglang:spec_accept_length` metric; vLLM
   `spec_decode_num_accepted_tokens/num_draft_tokens`).
5. KV pool from boot log (`max_total_num_tokens`); SS code + prose; TTFT;
   prefix-cache A/B (SGLang radix vs vLLM prefix caching — the never-measured
   RadixAttention win from our 2026-08-20 attempt).
6. Greedy determinism gate (3× byte-identical temp-0), tool-call round-trip
   (`--tool-call-parser qwen3_coder`), optional NIAH 4k/32k/128k — the tsw2k
   gate suite targets an OpenAI-compatible endpoint and works against SGLang's
   `/v1/chat/completions` too.
7. Report client-contract differences: SGLang splits thinking into
   `reasoning_content` (vLLM day-0 build used `message.reasoning`).

## Verification (commands actually run this session)

- Read the lane doc + every artifact it references (results JSON, prior
  sglang-vs-vllm report, miaai-merge.md/.REPORT, image-recipe.REPORT,
  PATCHES.md, PREFLIGHT-CHECKLIST, Dockerfile, launch scripts).
- Read-only ssh forge/anvil/ember/flame: `docker images` (all four),
  `docker inspect`/`docker history` on glm53-exl3:e2 + ghcr miaai image,
  `docker ps`, `nvidia-smi --query`. No mutation commands issued.
- Docker Hub registry + hub API: tag list (1000 tags), digests + push dates
  for qwen38flashnext / dev-* / spark; arm64 config blob labels of the
  current qwen38flashnext → commit 593134d1, created 2026-09-03.
- GitHub API/raw at 593134d1: commit metadata, full file tree,
  `qwen_sparse_attn_backend.py` (resolver gates + decode dispatch),
  `utils/common.py` (`is_sm120()==(12,0)`, `is_sm121()==(12,1)`),
  `kda_kernels/qwen38_qsa_sm121/{__init__,kernel,README}` (topology contract),
  `modelopt_quant.py` (mixed config, no FP8_BLOCK_SCALES),
  `modelopt_utils.py` (algo map, no MIXED_PRECISION entry),
  `configs/model_config.py` (MIXED_PRECISION→modelopt_mixed routing),
  `models/qwen4_exp.py` (PLE shard loader + fp8 auto-switch; 2131 lines),
  `spec_utils.py` + `mamba_radix_cache.py` (both clamp sites unbounded).
- PR #36566 via API: `state: closed, merged: false` (2026-08-26, CI ×3 failed);
  issues #36558 and #37326: both open (as of today).
- HF: nvidia + RadixArk config.json / hf_quant_config.json fetched and diffed
  (quant_algo, quantized_layers histograms, ignore/exclude lists,
  ple_embedding_dtype presence vs absence, ngram params identical).
- LMSYS day-0 blog + SGLang cookbook page fetched in full; pocharlies README
  (production 2-Spark recipe) fetched in full; RadixArk HF discussion 7;
  hasso5703 repo README.
- Live vLLM serve checked untouched (running before and after; a restart
  observed mid-session was external — zero mutating commands issued by this
  lane against any node).

Not done (per constraints): no docker builds, pulls, or launches; no cluster
writes; no installs; no commits. Deliverable written only under
`artifacts/qwen38-nvfp4-20260905/`.
