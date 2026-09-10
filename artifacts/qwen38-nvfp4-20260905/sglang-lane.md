# SGLang lane research — Qwen3.8-Flash-Next-NVFP4 on 4x DGX Spark

## Context
vLLM TP4+EP is LIVE and benched (results/qwen38-nvfp4-tp4-2026-09-05.json: 105.5@4 / 210.6@8 / 344.0@16 tok/s, SS 26.3, KV pool 5.06M, MTP accept 0.944). Jun wants the SGLang option benched too — "whichever gives best tok/s." RadixArk reportedly hit 40-100 t/s on SGLang with this model (2-node TP2), and MiaAI's repo has an SM121 QSA gate patch note for SGLang. GLM is DOWN, vLLM Qwen owns the quad right now on port 8000 — do not disturb it.

## Tasks (research + preparation only, NO launches, NO cluster changes)
1. Find the SGLang path for this exact checkpoint:
   - Does SGLang support Qwen3.8-Flash-Next (PLE n-gram embedding, QSA sparse attention, GDN/linear-attention hybrid, MTP) at all? Search SGLang GitHub (prs/issues/model support), RadixArk's repos/threads, blazux/MiaAI/tsw2k repos for sglang references, and the HF model card.
   - What image? (lmsysorg/sglang tags, any community SM121 build — note we have local glm53-sglang-sm121:dflash image on the sparks used as NCCL donor; check if it's usable, via ssh forge read-only `docker images`.)
   - Required patches for GB10/sm_121 (QSA gate patch, NVFP4 ModelOpt support in SGLang, PLE FP8, MTP).
   - Multi-node: can SGLang do TP4 across 4 nodes (it supports --nnodes/--node-rank dist-init)? EP? If only TP2-pairs realistic, document that as the lane shape (2 nodes = 2 endpoints, or TP2x2 with router?).
2. Deliver /home/jun/git/spark-bench/artifacts/qwen38-nvfp4-20260905/sglang-lane.REPORT.md: feasibility verdict (viable-today | needs-patches-listed | blocked-why), exact image tag/digest plan, patch list with provenance, launch command sketch for the recommended topology, expected tok/s with honest sourcing (cite RadixArk/MiaAI numbers precisely), risks, and what to measure for a fair comparison vs our vLLM numbers (same harness: usage-verified tokens, temp 0, thinking off, same prompt corpus).
3. Hard constraints: no cluster writes, no docker builds/launches, no taking down the running vLLM serve, no installs. Read-only ssh to forge allowed (docker images, docker inspect of existing sglang image). Write only under artifacts/qwen38-nvfp4-20260905/. No commits.

## Report
status: success|blocked|failed first line. This is a feasibility/plan deliverable.
