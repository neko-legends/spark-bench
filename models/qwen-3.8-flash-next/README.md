# Qwen 3.8 Flash Next

**2026-09-05: serving; stability testing in progress.** This is the official
NVIDIA NVFP4 checkpoint on four DGX Sparks, vLLM TP4+EP, MTP k=2.
Endpoint in this lab: `http://forge:8000/v1`; model ID `qwen3.8-flash-next`.

- [Current NVFP4 TP4 configuration, image identity and patch provenance](nvfp4-tp4/README.md)
- [First-pass benchmark scripts and limitations](benchmarks/README.md)
- [Dated measurement summary](../../results/qwen38-nvfp4-tp4-2026-09-05.json)
- [Retrieval smoke records](../../results/qwen38-resident-niah-smoke-2026-09-05.jsonl)
- [Overview and comparison table](../../README.md#qwen-3-8-flash)

## Reproduction boundary — read before launching

This repository contains the measured configuration and benchmark scripts, **not yet
all build inputs for the patched image**. Do not launch the upstream base image and
assume it has the same behavior. Do not silently substitute another quantization.

To recover this specific deployment on the original lab:

1. Check `/home/jun/launch-qwen38-tp4.sh` and its adjacent `patches/` directory on Forge.
2. Inspect the existing `local/qwen38-gb10:e1` image on every rank; compare its image ID
   with the recipe. Check that local checkpoint copies exist on all ranks.
3. If build inputs are needed, the original working copy retained them under
   `artifacts/qwen38-nvfp4-20260905/` and Forge's `/home/jun/qwen38-build/`.
   These paths are recovery pointers, **not files available in a fresh clone**.
4. If those assets are missing, stop and obtain the build recipe with upstream licenses;
   the source links and reviewed revisions in the recipe identify the reconstruction
   inputs but do not replace a tested build manifest.
5. Only after approval and an idle-cluster preflight, use the resident/full settings
   in the recipe. Confirm effective argv, KV pool, all-rank health and simple outputs.

A public, license-reviewed build bundle is still pending. Exact-token retrieval,
fail-closed repeated aggregate testing, tool/vision under load, mixed-prefill latency
and a multi-hour OOM-monitored soak remain qualification work. No 1M-context claim.
