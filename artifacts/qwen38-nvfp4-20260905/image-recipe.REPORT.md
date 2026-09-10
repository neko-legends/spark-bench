status: success

# image-recipe.REPORT.md — Qwen3.8-Flash-Next-NVFP4 TP4+EP image & launcher recipe

Researched and written 2026-09-05 on the eva-core box. Nothing on the sparks was
modified: no docker commands were run anywhere, no builds, no serves, no
transfers; the only cluster interaction was **read-only ssh to forge** (model
download status, NCCL staging, fabric, watchdogs) and public-API fetches
(GitHub, Docker Hub registry, Hugging Face). All files left uncommitted in
`artifacts/qwen38-nvfp4-20260905/`.

## What was verified (with real commands)

### The three patch repos (Task 1) — exist, cloned, read in full

| Repo | HEAD commit | What it contributes |
|---|---|---|
| blazux/qwen3.8-Flash-DGX | `b76890d5a033dd00166c792393d39cf908f56034` | Single-Spark patch stack: PLE mmap, FLA/GDN fixes, mamba race+guard, block_size fix, exact-topk, **det persistent_topk kernel (vllm#55122)**, fp8-KV, M%4 pad, hybrid mode |
| getrefined/Qwen3.8-Flash-Next-NVFP4-vLLM-DGX-Spark | `f736930b636d2dbb4c7f4746311cbac66d8d2a6e` | The **3-line PLE FP8 resolver** (`ple-force-fp8.patch`, `PLE_FORCE_FP8=1`, placed ABOVE the `isinstance(quant_config, Fp8Config)` gate); TP2+EP launcher shape with `FULL_DECODE_ONLY` + capture sizes; NCCL HCA exact-pin gotcha |
| tsw2k/Qwen3.8-Flash-Next-Quad-DGX-Sparks | `497a58e38b63f2223fb376901c3e4c5ede492efe` | The **4-node** recipe: TP4+EP launcher, Dockerfile (day-0 image + blazux stack), nofile=1M fix, GID auto-detect, preflight/gate-suite/watchdog, measured TP4 numbers, open-problems ledger |

Key extracted facts (all in the deliverables): tsw2k targets the day-0 image
vLLM 0.1.dev20073 (torch 2.13 cu130), layout `vllm/models/qwen3_8_flash_next/`;
the `qwen4_exp` rename (PR #53896, branch `peakcrosser7/vllm` `release/qwen38next`)
came after; the three TP4 fixes (EP mandatory at TP4 for NVFP4 MoE intermediate
padding; nofile 1M; never hardcode GID_INDEX); MTP k=2 default with 0.856
acceptance; MNBT 8192 default (2048 for deep prompts); `--mamba-block-size 1024`
moves the deep-prefill wall (vllm#54629); resident-PLE lane B boots at 0.78.

### Base image (Task 2)

- `vllm/vllm-openai:qwen38-flash-next` **exists** on Docker Hub (tag last pushed
  2026-08-26, 9.7 GB). Verified via the Docker Hub registry API with an auth
  token: the tag's `Docker-Content-Digest` today is **exactly the digest tsw2k
  and blazux pin**: `sha256:fc120ece0a388cc0aa1caad4a9f1cd92113484ab7ec2fd0efadd62585be05bf8`.
  Manifest list: arm64 `sha256:3b0e188ffceb3d07e09c3cb5215433a0020eacf02d7f882ed3a8bfd15454477e`,
  amd64 `sha256:0aea30240f3e3d9ffae8526643950e170eb5fa07fc427016a9dd90892afa2aa3`.
- Image config labels say `ai.vllm.build.commit = unknown` (local pipeline build) —
  the commit is not recorded in the image; identified from the repos as
  **vLLM 0.1.dev20073** on the day-0 `release/qwen38next` branch (PR #53896).
- **Model-card vLLM commit `d4d703caf908786416585ceb1f369e2e0363358b` is NOT in the
  image.** Fetched from GitHub: it is PR **#54882**, "[Bugfix][Model] Fix FP8 PLE
  loading in mixed ModelOpt checkpoints", committed **2026-09-03** — a week after
  the image tag (2026-08-26). It extends `_get_ple_embedding_quant_method` to
  accept `ModelOptMixedPrecisionConfig` (per-prefix `quant_algo == "FP8"` → PLE
  FP8 embedding method) — the **exact fix getrefined's 3-line patch backports**
  to the pre-rename day-0 image. The Dockerfile pins the day-0 digest (per spec)
  and bakes the backport in; conflict resolved by patching, not by silently
  trusting "any later commit" (which would mean a non-pinned, post-rename image
  where all the other GB10 patch paths break loudly).

### Model card + checkpoint (Task 3)

Fetched `README.md`, `config.json`, `generation_config.json`,
`hf_quant_config.json`, `model.safetensors.index.json` from
`huggingface.co/nvidia/Qwen3.8-Flash-Next-NVFP4/resolve/main`.

- **Arch**: `Qwen4ExpForConditionalGeneration` (model_type `qwen4_exp`),
  multimodal (vision_config present; image/video inputs), hybrid attention
  (GDN + QSA), 125B total / 6B active + 51B n-gram (PLE) + 4B MTP; 48 layers,
  512 experts (10 active, moe_intermediate 640), 24 heads / 2 KV heads,
  **native context 262,144**, extensible to 1M (YaRN, not default per spec).
- **Quantization (mixed)**: main routed experts NVFP4 W4A4 (group 16) + **MTP
  routed experts 128×128 block-scaled FP8** + **PLE n-gram per-tensor FP8**;
  ModelOpt v0.46.0; ~2.7× smaller than BF16. Files: 10 main shards + one
  `model-fp8-mtp-ple.safetensors` (**53.72 GB**), 25 files, 132.7 GB total.
- **Official serve command** (card): TP8, `--quantization modelopt`,
  `--max-model-len 262144`, `--reasoning-parser qwen3`, `--trust-remote-code`;
  generation_config: temp 1.0 / top_p 0.95 / top_k 20. The day-0 image registers
  the arch natively (trust-remote-code not needed; getrefined precedent).
- **PLE layout verified against the mmap patch's expectations** (HTTP Range
  request, parsed the safetensors header of `model-fp8-mtp-ple.safetensors`
  without downloading it): 128 tensors
  `model.language_model.layers.1.ple.ple_embedding.ngram_embedding.shard_N.weight`,
  **F8_E4M3, shape [2500012, 160]** (128 × 2,500,012 = 320,001,536 rows ≈ 48 GiB),
  plus one BF16 [1] `ngram_embedding.weight_scale` — exactly what
  `vllm_ple_mmap._find_shards()` matches and what `_read_scale` (BF16 path)
  consumes. The index.json maps all 128 shards to the single fp8-mtp-ple file;
  the mmap patch reads shard files by name from the index, so the layout works.
- Model download on forge: **running** (PID 1989213, snapshot_download,
  54G/132.7G at last read, log `/home/jun/models/qwen38-download.log`). Not touched.

### Cluster (read-only, forge)

- NCCL 2.30.7 staged at `~/nccl-2.30.7/libnccl.so.2.30.7` (253 MB) ✓; 2.3 TB free
  on the model NVMe ✓; fabric rail B up: `enP2p1s0f1np1` = 192.168.10.1/24,
  MTU 9000, HCA `roceP2p1s0f1` present, ~250 GID indices (auto-detect mandatory) ✓.
- GLM is **live** (container `glm53-exl3`, up 54 min) — untouched, and the launcher
  refuses to boot next to it. Watchdogs found and documented (not modified):
  `glm-cluster-watch.service` (active, eva-core user unit, **auto-relaunches GLM**)
  and `spark-forge-watchdog.timer` (user unit, currently inactive).

## Deliverables (where)

```
artifacts/qwen38-nvfp4-20260905/
├── Dockerfile.qwen38-gb10     # day-0 digest pin + vendored patch stack (patches 0-8)
├── launch-qwen38-tp4.sh       # GLM-shape TP4+EP launcher (preflight, NCCL staging,
│                               #   workers-first, crash-log snapshot, lanes)
├── PREFLIGHT-CHECKLIST.md     # Jun's spec line-by-line → where satisfied / conflicts
├── patches/
│   ├── PATCHES.md             # each patch → source repo + commit + why
│   ├── SHA256SUMS             # 19 files; kernel-det == blazux's ADD-checksum pins
│   ├── apply_ple_force_fp8.py  # our guarded port of getrefined's ple-force-fp8.patch
│   ├── ple-force-fp8.patch     # the original 3-line patch (provenance)
│   ├── vllm_ple_mmap.py, mamba_utils_guarded.py, patch_mamba_block_size.py,
│   │   patch_qsa_exact_topk.py, patch_ple_offload_modelopt.py,
│   │   patch_ple_offload_multinode.py, vllm_fp8_hybrid_modelopt.py,
│   │   test_ple_mmap_cpu.py, test_qsa_exact_topk_cpu.py, NOTICE
│   └── kernel-det/            # jschmied det persistent_topk (vllm#55122) sources
└── image-recipe.REPORT.md     # this file
```

Patch provenance: tsw2k @ `497a58e` (identical to blazux @ `b76890d`, sha-verified),
getrefined @ `f736930`, jschmied/qwen38-flash-next-gb10 @ `20f64c4c` (all six
files byte-identical to blazux's `ADD --checksum` pins). All vendored .py files
pass `py_compile`; both launcher script layers pass `bash -n`; the inner
serve-arg assembly was dry-run for all three cudagraph lanes (piecewise/full/eager,
head/headless, MTP on/off, moe-backend on/off).

## Spec-vs-reality conflicts (nothing silently dropped)

1. **`cudagraph FULL_DECODE_ONLY sizes [1,2,4,8]` vs `VLLM_PLE_MMAP=1`** — cannot
   coexist: the mmap PLE gather is CPU work + pageable H2D and dies inside graph
   capture (blazux: "never FULL*"). FULL_DECODE_ONLY is getrefined's
   *resident-PLE* shape. Both lanes are implemented: default
   `CUDAGRAPH_MODE=piecewise` + mmap (tsw2k-proven, gate-suite-passing, 5.2M-token
   KV pool), and `CUDAGRAPH_MODE=full PLE_MODE=resident` (exactly the spec's sizes,
   getrefiven-proven on TP2, ~12 GiB/rank PLE, GPU_MEM 0.78, smaller KV pool).
   Launcher refuses full+mmap. See PREFLIGHT-CHECKLIST.md.
2. **Model-card vLLM commit `d4d703caf` (#54882) not in the pinned image** —
   resolved by baking getrefined's pre-rename backport of the same fix into the
   image (patch 0). This is the sanctioned way to run this checkpoint on the
   day-0 image.
3. **`--moe-backend marlin`** (Jun's FlashInfer-CUTLASS-Xid-31 avoidance) is in
   no published recipe for this model; tsw2k runs EP + stock NVFP4 kernels fine.
   Implemented as the default (`MOE_BACKEND=marlin`), but it is **unverified on
   the day-0 image** — if the flag is rejected (argparse) or marlin-NVFP4 is
   unavailable on sm_121 in 0.1.dev20073, set `MOE_BACKEND=` and run the
   tsw2k-proven EP lane (see R3).
4. **`NCCL_CROSS_NIC=1`** — GLM and tsw2k both ran 0 on this class of fabric;
   spec wins (single-rail makes it mostly moot), env-overridable.
5. **Model card's `--quantization modelopt` / `--trust-remote-code` / TP8 sample**
   — not passed: quant config is auto-detected from the checkpoint (tsw2k/getrefined
   precedent), the arch is registered natively in the image, TP4+EP per spec.

## Risks (ranked)

- **R1 — FP8 MTP routed experts on the day-0 image (top risk).** The nvidia
  checkpoint adds `mtp.layers.0.mlp.experts` as a 128×128 block-scaled **FP8**
  config group (quant config `MIXED_PRECISION`, two groups), which none of the
  three repos tested — they served RadixArk's NVFP4 checkpoint. #54882 (the
  official fix for this checkpoint) only touches PLE, which suggests the rest
  worked on main; whether the day-0 image's ModelOpt config accepts the
  two-group mixed config is untestable without booting. **First-boot probe:** if
  loading dies in quant-config parsing or on MTP weights, fall back
  `MTP=0 ./launch-qwen38-tp4.sh` (MTP off; tsw2k explicitly notes MTP=0 is the
  fallback lane), and if the config itself is refused, the checkpoint needs a
  post-#54882 image (out of scope — flag to Jun).
- **R2 — deep-prefill wall (vllm#54629).** Prompts >~76.8k tokens can wedge the
  engine within a few requests (reproduces upstream, all PLE lanes, MTP=0).
  Native-262k lane with traffic under ~32k has never triggered it; mitigation
  `EXTRA_ARGS="--mamba-block-size 1024"` and MNBT 2048 for deep prompts. Run a
  watchdog (tsw2k's `fleet_watchdog.sh` pattern) on any production endpoint.
- **R3 — `--moe-backend marlin` on vLLM 0.1.dev20073**: flag availability and
  sm_121 NVFP4-marlin support unverified. Fallback: `MOE_BACKEND=` (stock EP,
  tsw2k-proven). Also related: `--no-enable-flashinfer-autotune` is already on.
- **R4 — GLM co-residency + auto-relaunch watchdogs.** glm-cluster-watch will
  re-launch GLM onto the nodes when it looks dead; it MUST be parked (by Jun/
  Depths, deliberately not by this recipe) before the Qwen38 lane takes the
  nodes. Launcher preflight refuses to boot next to any live GPU app or GLM/
  dspark container — it never kills anything.
- **R5 — image tag drift.** The `qwen38-flash-next` tag still resolves to the
  pinned digest today, but Docker Hub tags are mutable; the Dockerfile pins by
  digest so a re-pull is safe, and the build fails loudly (guarded greps +
  ast.parse in every patch step) if upstream ever re-cuts the tag under the same
  digest-referenced layers.
- **R6 — day-0 image is a `local` pipeline build** (`ai.vllm.build.commit=unknown`);
  version identity (0.1.dev20073) comes from the repos, not the image metadata.

## Runbook for Depths (build → fan out → boot)

Nothing below was executed; every step is a command for the operator.

**0. Preconditions.** Model download on forge complete (25 files, 132.7 GB —
`tail /home/jun/models/qwen38-download.log` should print DONE). Park the GLM
watchdog on the eva-core box: `systemctl --user stop glm-cluster-watch.service`
(and confirm `spark-forge-watchdog.timer` stays inactive). Retire GLM
(`~/launch-glm53-exl3-tp4.sh` teardown path or `docker rm -f glm53-exl3` on all
four nodes) — the Qwen38 lane needs the whole 128 GB pool per node. The GLM
container is up **right now**; the launcher preflight will refuse until it is gone.

**1. Build once, on forge** (~1 min after the base pull + ~15 s kernel build):

```bash
cd /home/jun/git/spark-bench/artifacts/qwen38-nvfp4-20260905   # or rsync the dir to forge first
docker build -f Dockerfile.qwen38-gb10 -t local/qwen38-gb10:e1 .
# optional self-checks inside the built image (no GPU, no weights needed):
docker run --rm --entrypoint python3 local/qwen38-gb10:e1 /opt/qwen38-patches/test_ple_mmap_cpu.py
docker run --rm --entrypoint python3 local/qwen38-gb10:e1 /opt/qwen38-patches/test_qsa_exact_topk_cpu.py
```

**2. Fan out the image + weights to anvil/ember/flame** (rsync daemon over the
CX7 rail at ~16 Gbps; ssh streams are AES-capped ~1 Gbps on GB10 — never scp
120 GB). On forge:

```bash
# image: tar named by image ID so a stale tar can never ship (tsw2k sync-image.sh)
ID=$(docker image inspect local/qwen38-gb10:e1 --format '{{.Id}}')
docker save local/qwen38-gb10:e1 | zstd -3 -T0 > /var/tmp/qwen38-image-${ID#sha256:}.tar.zst
# one-time rsyncd module on forge (read-only, rail B only; plaintext OK on the isolated L2 segment):
#   /etc/rsyncd.conf: [models] path=/var/tmp/... ; then
for h in 192.168.10.2 192.168.10.3 192.168.10.4; do
  ssh $h "rsync -a --partial rsync://192.168.10.1/models/$(basename /var/tmp/qwen38-image-*.tar.zst | tail -1) /var/tmp/ \
          && zstd -d < /var/tmp/$(basename /var/tmp/qwen38-image-*.tar.zst | tail -1) | docker load"
done
# weights: single rsync per worker from forge's NVMe copy (after download completes)
for h in 192.168.10.2 192.168.10.3 192.168.10.4; do
  ssh $h "rsync -a --info=progress2 --partial rsync://192.168.10.1/weights/qwen38-flash-next-nvfp4/ /home/jun/models/qwen38-flash-next-nvfp4/"
done
# (rsyncd module "weights" pointing at /home/jun/models; or plain `rsync -a ... $h:/home/jun/models/` — hours, not days, on the rail)
# verify everywhere: config.json + 11 safetensors + index on each node, and
docker image inspect local/qwen38-gb10:e1 --format '{{.Id}}'   # must print the same ID on all 4
```

**3. NCCL staging** — the launcher stages `~/nccl-2.30.7/libnccl.so.2.30.7` per
node automatically (present on forge already; donor image `local/glm53-exl3:e2`
on the others; each node needs it once).

**4. Boot (workers first, head last — the launcher does the ordering):**

```bash
./launch-qwen38-tp4.sh --wait        # default lane: PLE mmap + PIECEWISE + MTP k=2 + marlin
# spec lane (FULL_DECODE_ONLY sizes [1,2,4,8], resident PLE, 0.78):
CUDAGRAPH_MODE=full PLE_MODE=resident ./launch-qwen38-tp4.sh --wait
# OOM fallback: GPU_MEM_UTIL=0.78 (or 0.75); deep-prompt traffic: MAX_NUM_BATCHED_TOKENS=2048
# MTP fallback if R1 bites: MTP=0 ./launch-qwen38-tp4.sh --wait
```

Watch `docker logs -f qwen38-nvfp4` on a worker: ~8 min sharded load (the
fp8-mtp-ple tail is the slow part, not a hang), then warmup/graph capture, then
`Application startup complete`; `/v1/models` on http://192.168.10.1:8000.

**5. Gate.** Clone tsw2k @ `497a58e`, run its gate suite (implements Jun's bar):
`python3 evals/gate_suite.py --base http://192.168.10.1:8000 --model qwen3.8-flash-next --niah 4096,32768,131072`
— plus a 3rd temp-0 repeat (byte-identical), a tool-call round-trip
(`message.tool_calls` via qwen3_coder), SS/aggregate tok/s (bar: SS ≥28/t31,
agg ≥90@8, stretch 157@16), MTP accept ≥0.80 (vLLM metrics:
`spec_decode_num_accepted_tokens / num_draft_tokens`), KV pool size from the
boot log (`GPU KV cache size: N tokens`). Report per Jun: digest, flags,
SS/agg tok/s, KV pool, MTP accept, extra patches needed. One client note from
tsw2k: this build returns thinking in `message.reasoning`, not `reasoning_content`.

**6. Teardown/recovery.** `docker rm -f qwen38-nvfp4` on all four ranks before
ANY relaunch (a fresh rank that rendezvouses with a dying one hangs); crash logs
are snapshotted to `/home/jun/qwen38-crash-logs/` automatically. Re-run the
launcher for a full orchestrated relaunch (~15 min). Leave GLM's watchdogs
parked while this lane owns the nodes.

---

# MiaAI merge (2026-09-05, appended)

Merged learnings from **MiaAI-Lab/Qwen3.8-Flash-Next-Dual-DGX-Sparks** @
`c2325b22602b51a5faf55fc2bebccc34f3f80b9f` (TP2+EP+MTP3 on 2 Sparks) into our TP4
recipe. This matters more than a normal community recipe: MiaAI is the same lab
behind our production GLM EXL3 recipe, and — critically — their repo has **actually
served the official nvidia/Qwen3.8-Flash-Next-NVFP4 checkpoint on the same day-0
image** (vLLM `v0.1.dev20073+g8e685d198`, corroborating our version identification
in R6) and published the three fixes it needed. Nothing was built, booted, or
committed; every claim below was verified with real commands (fetches from HF/GitHub
+ offline dry-runs; see "verification" at the end).

## Headline: risk R1 (FP8 MTP on the nvidia checkpoint) is CLOSED

Our top risk was "the nvidia checkpoint's FP8 MTP routed experts may not load on
the day-0 image; fallback MTP=0". MiaAI hit exactly this and fixed it with two
patches, both now in our recipe:

1. **MTP layer-index alias** (`patches/patch_checkpoint_config.py`, vendored
   verbatim from MiaAI, AGPL-3.0-or-later — internal use only). vLLM builds the
   MTP draft layer at the **absolute** index (`mtp.layers.48` for
   num_hidden_layers=48) and matches quantization metadata by exact string; the
   nvidia checkpoint records only `mtp.layers.0` (verified in its config.json +
   hf_quant_config.json, both fetched from HF today). The alias script patches
   BOTH files (vLLM reads the legacy file on the draft-model path), mirrors
   `config_groups.targets`, never touches the model copy (patched configs are
   bind-mounted over the container's config paths), and is idempotent.
2. **FP8_BLOCK_SCALES MoE dispatch** (`patches/patch_modelopt_fp8_block_moe.py`,
   our guarded in-place port of MiaAI's patch; original pinned by sha256 in
   PATCHES.md). The MTP experts are 128×128 block-scaled FP8 (config group_1:
   `{num_bits 8, group_size 128}`, algo `FP8_BLOCK_SCALES` — verified); the stock
   `ModelOptMixedPrecisionConfig.get_quant_method` returns None for that algo →
   silently unquantized MoE → dies ~7 min into loading with
   `Layer mtp.layers.48.mlp.experts has no parameter 'w2_weight_scale_inv'`.
   The gap is NOT image-specific (upstream vLLM, incl. model-card commit
   `d4d703caf`, has no branch either — upgrading the image does not fix MTP).
   The patch routes to vLLM's own `Fp8MoEMethod`, block size read from the
   checkpoint's `group_size` (refuses to guess — a wrong shape misapplies scales
   silently).

**Evidence MTP works with these on this image+checkpoint** (MiaAI, TP2+EP,
262144 ctx, GMU 0.835, batch-1 greedy): MTP=3 → 52.1 tok/s vs 24.5 without
(2.13×), 72.8% draft acceptance, per-position 89%/74.5%/60% — the decaying curve
that proves the block shape is right. Our k=2 default stays (tsw2k measured 0.856
acceptance at k=2 on the same hardware class at TP4).

## What was adopted

| Change | Where | Why |
|---|---|---|
| MTP layer-index alias (runtime) | `launch-qwen38-tp4.sh`: new staging section runs `patches/patch_checkpoint_config.py` on forge against the mounted checkpoint, streams the patched configs to every node, bind-mounts them over `/models/qwen38/{config,hf_quant_config}.json` | Closes the `mtp.layers.0` → `mtp.layers.48` string-match miss (verified on the real config); MiaAI's pattern, NVMe copy untouched |
| FP8_BLOCK_SCALES dispatch (image patch 9) | `Dockerfile.qwen38-gb10` step 9 + `patches/patch_modelopt_fp8_block_moe.py` | Closes the unbuildable-MTP-MoE gap (see above); anchors verified against day-0 source @ `d4d0f73ef171` (each exactly once); idempotent |
| fp8 KV cache (image patch 10, opt-in lane) | `Dockerfile.qwen38-gb10` step 10 (blazux `patch_qsa_fp8_kv.py`, vendored verbatim, Apache-2.0) + `KV_CACHE_DTYPE` env in launcher | INERT at `auto` (constexpr-eliminated); enables `KV_CACHE_DTYPE=fp8` → ~1.7× KV pool (MiaAI-measured on this checkpoint: 2,131,159 → 3,652,200 tokens, 12/12 reasoning+needle smoke, no decode cost measured); blazux claims ~1.9×. Applied in blazux's canonical slot (after exact-topk + hybrid, before qsadet) — the order their Dockerfile proves on this same digest-pinned image. Default stays `auto` (quality trade, see risks) |
| MTP algo fast-fail preflight | launcher, in the alias staging section | MiaAI pattern: fails in SECONDS if the MTP expert algo is unbuildable instead of ~7 min into the load. Verified: prints `FP8_BLOCK_SCALES` on our checkpoint (supported via patch 9) |
| `--mm-encoder-tp-mode data` | launcher ARGS | Vision MLP intermediate 4304 is not %16 after TP split (2152@TP2, 1076@TP4 — worse at our TP4); MiaAI-verified on this checkpoint+image. Avoids a class of TP-split vision crashes |
| `--cap-add SYS_NICE` | launcher docker run | MiaAI container shape; harmless, helps NCCL thread priorities |
| `ALL2ALL_BACKEND` env (default empty = stock) | launcher | MiaAI measured `allgather_reducescatter` at TP2+EP on the same image; kept opt-in because tsw2k's TP4 gate-suite pass ran stock |
| YaRN `text_config` nesting note | PREFLIGHT-CHECKLIST.md | MiaAI discovery: top-level `rope_parameters` overrides never reach `text_config` — all earlier "1M context" runs were unscaled-rope no-ops. Only matters if the YaRN lane is ever exercised (our default is native 262144) |
| Version identity corroboration | this report | MiaAI's running container reports `v0.1.dev20073+g8e685d198` on the same tag — confirms R6's identification of the day-0 image |

## What was rejected (and why)

- **MiaAI's `patch_ple_layer.py`** (PR #53899-style dtype dispatch + NVFP4-PLE
  runtime): solves the same PLE gap our patch 0 solves, but needs
  `text_config.ple_embedding_dtype` (which the nvidia checkpoint doesn't declare —
  their stack pairs it with `detect_ple_dtype.py` + `--hf-overrides`). Our
  env-forced `PLE_FORCE_FP8=1` covers the nvidia checkpoint's FP8 PLE directly;
  their NVFP4-PLE machinery targets the local-inference-lab checkpoint we don't
  serve. Equivalent for our checkpoint; kept ours.
- **`patch_modelopt_mxfp8.py`** (MXFP8 shape fallback): the nvidia checkpoint has
  NO MXFP8 layers (verified: quant_algo histogram = NVFP4×48, FP8×1,
  FP8_BLOCK_SCALES×1; dense is BF16). Only needed for RadixArk/local-inference-lab.
- **Reduced-vocabulary MTP drafting**: output-safe but a measured trade
  (acceptance 56.5% → 47.8% balanced, `copy` task below baseline); MiaAI ships it
  off by default and calls it "a real trade, not a free win". Not vendored.
- **QSA gb10 launch profiles**: "a starting point, not a result" per MiaAI; their
  default is `stock`. Future benchmarking candidate, not now.
- **FP8-dense hybrid checkpoint**: builds a different checkpoint; we serve the
  official one as published (Jun's requirement); MiaAI hasn't quality-validated it.
- **MiaAI's PLE offload stack**: NVFP4-PLE-specific; MiaAI measured it needs ~51 GB
  free CPU RAM and OOMs on their box — same conclusion as tsw2k's. Our lanes stand.
- **NFS weight sharing**: spec forbids NFS for the PLE mmap lane (per-node NVMe
  copy mandatory). Rejected.
- **Hardcoded `NCCL_IB_GID_INDEX=3` + `NCCL_IB_AUTO_DETECT=0`**: REJECTED — tsw2k
  caught GID index drifting 4↔3 after a link bounce on this fabric class (~250
  GID indices on forge). Auto-detect stays.
- **TP2-shaped defaults** (GMU 0.835, MTP=3, MAX_NUM_SEQS=8, port 8888,
  `--safetensors-load-strategy lazy`, `NCCL_CUMEM_ENABLE` unset): our TP4 defaults
  stay tsw2k-proven; `lazy` documented as an EXTRA_ARGS option.
- **EP dropped?** No — MiaAI also runs EP ("required for NVFP4") and demonstrates
  nothing about TP-without-EP. `--enable-expert-parallel` stays mandatory.

## Final patch list (patches/, 22 checksummed files)

0. PLE FP8 resolver (getrefined, env `PLE_FORCE_FP8=1`) — unchanged
1. PLE mmap (tsw2k/blazux, `VLLM_PLE_MMAP=1`) — unchanged
2. FLA shmem + num_warps (sed, always on) — unchanged
3. Mamba race + guard (always on) — unchanged
4. Prefix-caching block_size (always on) — unchanged
5. Exact QSA top-k (env) — unchanged
5b. Deterministic persistent_topk kernel (default on) — unchanged
6. FP8 hybrid mode shim (env, unused lane) — unchanged
7. PLE offload ModelOpt gate — unchanged
8. PLE offload multi-node — unchanged
9. **NEW: FP8_BLOCK_SCALES routed experts → Fp8MoEMethod** (MiaAI port, always on)
10. **NEW: fp8_e4m3 KV cache on QSA** (blazux, inert at `auto`, lane `KV_CACHE_DTYPE=fp8`)
11. **NEW (runtime, not baked): MTP layer-index alias** (MiaAI, launcher-staged
    config overlay; `--mtp-moe-algo` preflight included)

Application order (matters): 0 → 1 → 2 → 3 → 4 → 5 → 7 → 8 → 9 → 6 → 10 → 5b,
then patch 11 at launcher time. Patch 9 must precede the hybrid EOF-append on the
same file; patch 10 sits in blazux's canonical slot (after exact-topk + hybrid,
before qsadet).

## Final launch lanes

| Lane | Env | Notes |
|---|---|---|
| **Default** | (no env) | TP4+EP, PLE mmap (32 workers, prewarm), PIECEWISE + splitting ops, MTP k=2 (now loadable: patches 9+11), moe-backend marlin, KV auto, `--mm-encoder-tp-mode data`, image patch 10 inert |
| Spec lane | `CUDAGRAPH_MODE=full PLE_MODE=resident` | FULL_DECODE_ONLY [1,2,4,8] (getrefined shape; MiaAI also runs FULL_DECODE_ONLY+resident on this checkpoint at TP2, sizes 1–64) |
| KV-headroom lane | `KV_CACHE_DTYPE=fp8` | ~1.7× KV pool via image patch 10; validate quality on your workload first |
| OOM fallback | `GPU_MEM_UTIL=0.78` (or 0.75) | unchanged |
| MTP fallback | `MTP_TOKENS=0` | unchanged (tsw2k lane); should no longer be needed for load failures |
| Deep prompts | `MAX_NUM_BATCHED_TOKENS=2048` + `EXTRA_ARGS="--mamba-block-size 1024"` | unchanged (vllm#54629 wall) |
| EP all2all experiment | `ALL2ALL_BACKEND=allgather_reducescatter` | MiaAI TP2-measured; untested at TP4 |

## New / updated risks

- **R1 (FP8 MTP) → RESOLVED** by patches 9 + 11, with MiaAI's TP2 measurements as
  evidence. Residual: their measurement is TP2+EP on 2 nodes; TP4 on 4 nodes is
  untested (the patches are TP-agnostic — aliasing is config-only, the dispatch
  branch is per-layer). First boot should still watch the MTP drafter load.
- **R-NEW-1 (fp8-KV quality trade)**: quantized keys perturb which blocks the QSA
  sparse indexer *selects* (not just attention output). The upstream approach's
  origin reports a 6/6 → 2/6 long-reasoning regression that did NOT reproduce in
  MiaAI's 12-task smoke test. Default lane stays `auto`; anyone enabling
  `KV_CACHE_DTYPE=fp8` must re-validate reasoning on their own workload
  (MiaAI's `bench/reasoning_check.py` pattern is the right tool).
- **R-NEW-2 (patch 10 anchor composition)**: blazux's fp8-KV patch touches the
  image-only `nvidia/qsa.py`; its owner-file half could not be verified offline
  (the public repo's file diverged post-rename). It is image-proven by
  construction — blazux's Dockerfile applies it to the same digest-pinned image
  in the same slot we use — and our Dockerfile step re-ast.parses both files, so
  a moved anchor fails the build loudly. The `ops/qsa.py` half WAS verified to
  compose after our exact-topk patch (offline dry-run on the day-0 branch source).
- **R-NEW-3 (patch 9 anchors)**: verified against the day-0 commit
  `d4d0f73ef171` source (each anchor exactly once) and the patch is idempotent
  with ast.parse gating, but the image's actual modelopt.py is a local pipeline
  build — if it diverges from the branch, the build fails loudly (guarded).
- **R-NEW-4 (AGPL)**: two files vendored from MiaAI
  (`patch_checkpoint_config.py` verbatim; the original of our patch 9 port) are
  AGPL-3.0-or-later. Internal cluster use only; do not publish these artifacts
  without honoring AGPL. Everything else in the stack is Apache-2.0 lineage.
- **R-NEW-5 (`--mm-encoder-tp-mode` flag)**: MiaAI passes it on the same image
  (verified on their running container), so argparse acceptance is proven; if the
  flag were ever rejected the container dies at startup with a clear argparse
  error (no silent failure mode).
- R2–R6 stand unchanged (deep-prefill wall, marlin-on-day-0, GLM watchdogs,
  tag drift — mitigated by digest pin, local-build version identity).

## Verification (real commands, this session)

- Cloned MiaAI @ `c2325b2` and blazux @ `b76890d`; read README/CHANGELOG/start.sh/
  patches in full.
- Fetched `config.json` + `hf_quant_config.json` from
  `huggingface.co/nvidia/Qwen3.8-Flash-Next-NVFP4` and verified MiaAI's claims
  against the real checkpoint: `num_hidden_layers=48`; `ple_embedding_dtype`
  absent; PLE group `num_bits=8`; MTP algo `FP8_BLOCK_SCALES` with
  `group_size=128`; mtp entries recorded only as `mtp.layers.0.*`; NO MXFP8
  anywhere (histogram NVFP4×48 / FP8×1 / FP8_BLOCK_SCALES×1).
- Ran their `patch_checkpoint_config.py` for real: `--mtp-moe-algo` prints
  `FP8_BLOCK_SCALES`; the alias patch outputs both patched files with
  `mtp.layers.48.mlp.experts` added (config.json + hf_quant_config.json +
  config_groups targets mirrored); idempotent re-run is a no-op; diff is
  strictly additive.
- Ran their `detect_ple_dtype.py` on the real config: prints `float8_e4m3fn`
  (consistent with our safetensors-header verification — our env-forced patch 0
  covers the same gap without needing the override).
- Fetched day-0-branch `modelopt.py` (`peakcrosser7/vllm` `release/qwen38next`,
  commit `d4d0f73ef171` "Support Qwen3.8-Flash-Next", 2026-08-26): patch 9's two
  anchors appear exactly once each, `FP8_BLOCK_SCALES` absent. Dry-ran our
  ported patcher on it: applies, parses, idempotent.
- Dry-ran patch composition on day-0-branch QSA sources: our exact-topk patch →
  blazux's fp8-KV patch (ops/qsa.py half applies cleanly, output parses; the
  owner half is image-only — see R-NEW-2).
- `py_compile` on all three new patch files; `bash -n` on the launcher; the new
  launcher staging block executed end-to-end against the real checkpoint config
  (local-only SSH list) producing correct CFG_MOUNTS; the inner serve-arg
  assembly dry-run for piecewise/full/eager × MTP on/off × moe on/off ×
  KV auto/fp8 × all2all opt-in (empty MOE_BACKEND correctly omits the flag).
- `sha256sum -c` over the regenerated SHA256SUMS (22 files) passes; kernel-det
  pins unchanged and still byte-identical to blazux's ADD-checksums.

Not done (per constraints): no docker builds, no boots, no cluster mutation, no
git commits. GLM was already down before this session (per task state).
