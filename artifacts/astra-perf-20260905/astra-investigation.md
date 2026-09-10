# GLM 5.3 Flash EXL3 TP4 performance investigation — 2026-09-05

## Goal
Jun explicitly requests a fresh GPT Astra investigation to make the current C-verified GLM 5.3 Flash serve faster on four DGX Sparks. Find implementable, evidence-backed optimizations, not generic tuning suggestions. You are the Astra performance investigator. This phase is read-only on serving systems; no downtime or benchmark traffic yet. Produce a concrete first experiment/patch proposal for Depths to approve and supervise.

## Read first
- /home/jun/git/spark-bench/README.md (GLM section, especially C verified and dead ends)
- /home/jun/git/spark-bench/models/glm-5.3-flash/exl3-tp4/README.md
- /home/jun/git/spark-bench/artifacts/astra-perf-20260905/live-audit.txt
- /home/jun/git/spark-bench/artifacts/astra-perf-20260905/launcher.snapshot.sh
- /home/jun/git/spark-bench/results/c4-sweep-20260904-0030/SUMMARY.md
- /home/jun/git/spark-bench/scripts/bench_c4_steady.py and bench_decode_full.py

## Tasks (bounded, aim <=40 minutes)
1. Reconstruct the actual serving path. SSH forge is available (management only). Read /home/jun/launch-glm53-exl3-tp4.sh, /tmp/glm53-exl3-start.sh and runtime patches under /home/jun/glm53-exl3-recipe/overlay and /tmp/patch_*.py. Use docker exec glm53-exl3 for read-only inspection of the installed vLLM/EXL3/DFLASH implementation. Copy selected source into this artifact directory if useful. Do not dump personal inference logs, credentials, env secrets, memory or transcripts.
2. Trace hot decode path, not just launcher knobs: scheduler_decode_floor, drafter_group, spinwait, fat-expert dispatch thresholds, speculative verification batch shapes, graph/eager boundaries, CPU syncs, per-rank communication, EXL3 decode vs prefill kernels. Determine whether small verifier batches unintentionally hit the fat-prefill kernel or graph breaks, and identify precise branches/lines. Verify hypotheses from source, label unmeasured ones.
3. Check upstream public repositories/pinned commit changes selectively for relevant optimizations (no blind upgrades). Review which prior tunings are already tried/dead ends.
4. Give <=5 ranked candidates, predicted mechanism and falsification test, exact file/line or knob, applicability to C1/C4/prefill/mixed traffic, stability risks, rollback. Include one strongest first experiment. A local candidate diff under artifacts is allowed, but never modify canonical launcher/patches or live container. No synthetic invented measurements.
5. Separate the historical 253 aggregate comparison from current measurements: single cold-boot ablations do NOT prove the regression is caused collectively by all patches. Request paired, repeated baselines.

## Constraints
- No server restarts, live patches, daemon/config changes, GPU clock/memory/network changes, cache flushes, benchmark requests, dependency installs or model downloads.
- Do not spawn other workers. Do not use Sparks inference; keep cluster quiet.
- Public code + operational technical configuration only; no personal records or secrets.
- Preserve GPU_MEM_UTIL <=0.80, NCCL autotune, current weights/quant/context capabilities in proposals unless clearly marked as a separate tradeoff (not comparable speed gain).
- Source-of-truth public repo HEAD 4bc912877d9f0adfde29e0d4a993378a3ee9974b. No commits/pushes. Write only under artifacts/astra-perf-20260905/.

## Deliverable
Write /home/jun/git/spark-bench/artifacts/astra-perf-20260905/astra-investigation.REPORT.md, starting status: success|blocked|failed. Report source evidence, actual findings vs hypotheses, ranked proposals, exact next experiment and safeguards. Also include any local candidate diff path. This is an investigation success, not a performance improvement claim. Return to Depths for implementation and controlled measurement.
