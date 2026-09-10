status: success

# miaai-merge.REPORT.md — MiaAI dual-Spark learnings merged into the TP4 recipe

Executed 2026-09-05 per `miaai-merge.md`. All tasks (1–5) done; all hard
constraints respected: **no docker builds, no boots, no cluster mutation, no git
commits**; every touched Python file passes `py_compile` / target checks, both
launcher layers pass `bash -n`, and the new launcher logic was dry-run against
the real checkpoint config.

## What changed (and where)

### New files (artifacts/qwen38-nvfp4-20260905/patches/, provenance in PATCHES.md)

| File | Source | What it does |
|---|---|---|
| `patch_modelopt_fp8_block_moe.py` | our guarded in-place port of MiaAI-Lab/Qwen3.8-Flash-Next-Dual-DGX-Sparks @ `c2325b22602b51a5faf55fc2bebccc34f3f80b9f` (original sha256 `00a01640…` recorded in PATCHES.md; AGPL-3.0-or-later, internal use) | Image patch 9: `FP8_BLOCK_SCALES` routed experts → `Fp8MoEMethod` (block size from the checkpoint's `group_size`). Required for MTP on the nvidia checkpoint — its MTP experts are 128×128 block-scaled FP8, which the stock dispatch (and upstream vLLM, incl. model-card commit `d4d703caf`) cannot build, yielding a silently unquantized MoE that dies ~7 min into loading. |
| `patch_qsa_fp8_kv.py` | blazux/qwen3.8-Flash-DGX @ `b76890d` (Apache-2.0), vendored verbatim (byte-identical, cmp-verified) | Image patch 10: fp8_e4m3 KV cache on the QSA path. INERT at `--kv-cache-dtype auto` (constexpr-eliminated); enables the `KV_CACHE_DTYPE=fp8` lane (~1.7× KV pool, MiaAI-measured on this checkpoint at TP2). |
| `patch_checkpoint_config.py` | MiaAI @ `c2325b2`, vendored verbatim (AGPL-3.0-or-later, internal use) | Runtime patch 11: MTP layer-index alias (`mtp.layers.0` → `mtp.layers.48`) for config.json + hf_quant_config.json, plus `--mtp-moe-algo` fast-fail preflight. Idempotent; never modifies the model copy. |

`SHA256SUMS` regenerated: 22 files, `sha256sum -c` passes (kernel-det pins
unchanged, still byte-identical to blazux's ADD-checksums).

### Updated files

- **Dockerfile.qwen38-gb10** — added step 9 (fp8-block-MoE, before the hybrid
  EOF-append on the same file) and step 10 (fp8-KV, in blazux's canonical slot:
  after exact-topk + hybrid, before qsadet — the order blazux's own Dockerfile
  proves on the same digest-pinned image); header patch list updated.
- **launch-qwen38-tp4.sh** — new "MTP layer-index alias staging" section
  (generates patched configs on forge from the mounted checkpoint, streams them
  to all nodes, bind-mounts them over `/models/qwen38/{config,hf_quant_config}.json`;
  includes the MTP-expert-algo fast-fail preflight); `KV_CACHE_DTYPE` now
  env-overridable (default `auto`, `fp8` lane); `--mm-encoder-tp-mode data`
  (MiaAI-verified — vision MLP 4304 not %16 after TP split); `--cap-add SYS_NICE`;
  `ALL2ALL_BACKEND` opt-in (default stock); hf_quant_config.json presence warn in
  preflight; header/lanes docs updated.
- **patches/PATCHES.md** — entries 9/10/11 with repo+commit+sha256 provenance and
  license notes; "deliberately NOT in this image" rewritten (MiaAI rejects with
  reasons); application-order section updated (0→1→2→3→4→5→7→8→9→6→10→5b, then 11
  at launcher time).
- **PREFLIGHT-CHECKLIST.md** — patches table gains rows 9/10/11 (R1 marked
  closed), serve-flags table gains mm-encoder-tp-mode + KV dtype lane, and a new
  "MiaAI merge notes" section (YaRN `text_config`-nesting discovery, EP stays
  mandatory, adopt/reject summary).
- **image-recipe.REPORT.md** — appended a dated "MiaAI merge (2026-09-05)"
  section (adopted / rejected / final patch list / final lanes / new risks /
  verification log); history untouched; first line still `status: success`.

## Headline result

**Top risk R1 (FP8 MTP experts on the day-0 image) is closed.** MiaAI has served
the official nvidia checkpoint on the same day-0 image and the two fixes it
needed are now ours: the config alias (patch 11) + the FP8_BLOCK_SCALES dispatch
(patch 9). MiaAI's TP2+EP measurements with both: MTP=3 → 2.13× decode, 72.8%
draft acceptance (decaying per-position curve = block shape proven). EP stays
mandatory (MiaAI also runs EP; nothing demonstrates TP-without-EP). Our k=2
default stands (tsw2k TP4 measured 0.856 acceptance).

## What I verified (real commands)

1. Cloned MiaAI @ `c2325b2` + blazux @ `b76890d`; read README, CHANGELOG,
   start.sh, .env.sample, HANDOFF doc, and all patch files in full.
2. Fetched the nvidia checkpoint's `config.json` + `hf_quant_config.json` from HF
   and confirmed every MiaAI claim against the real files: `num_hidden_layers=48`,
   `ple_embedding_dtype` absent, PLE group `num_bits=8`, MTP algo
   `FP8_BLOCK_SCALES` `group_size=128`, mtp recorded only as `mtp.layers.0.*`,
   no MXFP8 anywhere (NVFP4×48 / FP8×1 / FP8_BLOCK_SCALES×1).
3. Ran their `patch_checkpoint_config.py` for real: `--mtp-moe-algo` →
   `FP8_BLOCK_SCALES`; alias patch adds `mtp.layers.48.mlp.experts` to both files
   (+ config_groups targets); diff strictly additive; idempotent re-run no-op.
   `detect_ple_dtype.py` → `float8_e4m3fn` (our env-forced patch 0 covers the
   same gap, so their dtype-override machinery is not needed).
4. Fetched the day-0 branch `modelopt.py` (peakcrosser7/vllm @ `d4d0f73ef171`,
   "Support Qwen3.8-Flash-Next", 2026-08-26): patch 9 anchors each appear exactly
   once, `FP8_BLOCK_SCALES` absent; dry-ran our ported patcher — applies, parses,
   idempotent.
5. Dry-ran patch composition on day-0-branch QSA sources: our exact-topk patch →
   blazux fp8-KV patch — the `ops/qsa.py` half applies cleanly and parses (the
   `nvidia/qsa.py` half is image-only and could not be verified offline; it is
   image-proven by blazux's Dockerfile on the same digest pin, and our build step
   ast.parses both files so a moved anchor fails the build loudly).
6. `py_compile` all patch .py files; `bash -n` on the launcher; `sha256sum -c`
   (22 files) passes; the new launcher staging block executed end-to-end against
   the real checkpoint config (local-only SSH list) producing correct CFG_MOUNTS
   and aliased configs; inner serve-arg assembly dry-run across
   piecewise/full/eager × MTP on/off × moe on/off × KV auto/fp8 × all2all opt-in
   (empty MOE_BACKEND correctly omits the flag; rank≠0 gets `--headless`).

## Risks (new; full list in the appended report section)

- fp8-KV lane is a **quality trade** (sparse-indexer block selection perturbed by
  quantized keys; upstream origin reports a long-reasoning regression that did
  not reproduce in MiaAI's 12-task smoke) — default stays `auto`; re-validate
  before trusting `KV_CACHE_DTYPE=fp8`.
- Patch 10's owner-file anchors are image-only (verified by construction via
  blazux + guarded at build time); patch 9 anchors verified against the
  day-0-commit source, also build-time guarded. Both fail loudly, never silently.
- Two vendored files are **AGPL-3.0-or-later** (MiaAI lineage) — internal use
  only; do not distribute these artifacts without honoring AGPL.
- MiaAI's MTP evidence is TP2+EP on 2 nodes; TP4 on 4 nodes untested (patches
  are TP-agnostic). First boot should still watch the MTP drafter load.
- Pre-existing R2–R6 unchanged (deep-prefill wall, marlin-on-day-0, GLM
  watchdogs, mutable tag — digest-pinned, local-build version identity now
  corroborated by MiaAI's `v0.1.dev20073+g8e685d198`).
