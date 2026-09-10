# Merge MiaAI-Lab dual-Spark Qwen3.8-Flash-Next learnings into our TP4 recipe

## Context
Jun clarified: the pasted spec is guidance, not gospel. Real requirement: serve the OFFICIAL nvidia/Qwen3.8-Flash-Next-NVFP4 checkpoint, TP4 on 4× DGX Spark, working GREAT. A new reference repo exists: https://github.com/MiaAI-Lab/Qwen3.8-Flash-Next-Dual-DGX-Sparks (dual-Spark; we want TP4 NVFP4). Prior work is in /home/jun/git/spark-bench/artifacts/qwen38-nvfp4-20260905/ — READ FIRST: image-recipe.REPORT.md, Dockerfile.qwen38-gb10, launch-qwen38-tp4.sh, PREFLIGHT-CHECKLIST.md, patches/PATCHES.md.

## State
- Checkpoint (nvidia/, 132.7GB) already on all 4 nodes at /home/jun/models/qwen38-flash-next-nvfp4 (verified byte-identical).
- GLM serve is DOWN (Jun's call — quad is dedicated to Qwen benching).
- Our recipe is built on blazux + getrefined + tsw2k. MiaAI is the same lab behind the GLM EXL3 recipe we run in production — their Qwen3.8 repo likely has the most battle-tested GB10 patches.

## Tasks
1. Clone and read MiaAI-Lab/Qwen3.8-Flash-Next-Dual-DGX-Sparks fully: Dockerfile/patches/launcher/configs. Note their pinned vLLM version, patch stack, launcher env, EP/TP choices, MTP config, PLE handling, cudagraph choices, memory utilization, and any NVFP4-vs-their-quant differences (their repo may target a different quant — we're locked to nvidia NVFP4).
2. Diff their patch stack against our vendored one (patches/). Identify: patches they have that we lack (candidate additions), patches we have that they omit (check whether ours conflict), and launcher/env divergences worth adopting (NCCL, PLE mmap workers, prewarm, spec config, cudagraph mode, max-num-seqs/batched-tokens).
3. UPDATE the deliverables in place: Dockerfile.qwen38-gb10, patches/ (add new vendored files with provenance in PATCHES.md — repo + commit + sha256), launch-qwen38-tp4.sh, PREFLIGHT-CHECKLIST.md. Where MiaAI and the pasted spec conflict, prefer measured/community-verified practice and note it. TP4 stays mandatory; EP stays unless MiaAI demonstrates NVFP4 TP4 loads without it (report, don't drop silently).
4. Keep the launcher's cudagraph/PLE-mmap guard logic; if MiaAI shows a working combination, make it the default lane and document.
5. Do NOT build images, boot anything, or commit to git. py_compile/bash -n everything you touch.

## Report
Append to image-recipe.REPORT.md a dated "MiaAI merge" section (do not rewrite history): what was adopted, what was rejected and why, final patch list, final launch lanes, and any new risks. Ensure first line still reads status: success|blocked|failed.
