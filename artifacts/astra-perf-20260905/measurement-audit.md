# Independent measurement audit — GLM throughput

## Goal
Read-only independent reviewer of the public spark-bench benchmark evidence. Main Astra investigator separately audits live kernel/serving source. Your task is to design honest, reproducible measurement for a new optimization campaign. No implementation or live requests.

## Read first
/home/jun/git/spark-bench/README.md GLM section; scripts/bench_c4_steady.py; scripts/bench_decode_full.py; results/verify-C-c4-2026-09-03.json; results/verify-C-decode-2026-09-03.json; results/c4-sweep-20260904-0030/ (SUMMARY.md and raw JSON); any Aug 28 referenced benchmark scripts/results needed to compare the claimed 253 tok/s to today's 128.9.

## Work
1. Audit aggregate tok/s formula, TTFT exclusion, sample length, actual usage vs SSE chunk counts, warmup, thinking tokens, cache handling, synchronization, EOS/length finishes, timeout/missing-run handling. Detect bugs and identify old-vs-new noncomparability with concrete file/line/data evidence.
2. The prior summary claimed removing any patch gains ~25% and therefore regression shared across patch set. Treat that causal conclusion as UNPROVEN; one cold-after-boot run/config is confounded. Explain whether the data supports any causal ranking.
3. Propose a minimal safe benchmark protocol: repeated warmed current baseline; controlled idle/quiescence; matched prompts with actual tokenizer usage; separate generated tok/s vs end-to-end rate and TTFT/inter-token latency; C1/C4 structured/code/prose; spec acceptance deltas and per-rank memory/clock telemetry. Bound cost/runtime and prevent future overwrite of dated outputs (bench_decode_full.py is known to write a hardcoded dated output). Don't recommend cache flushes on the live shared serve.
4. Design next A/B/A experiment criteria, variance threshold and correctness/mixed-prefill guards to protect serving performance/capability. Identify exact minimal harness changes needed for a builder.

## Hard constraints
No ssh, benchmark traffic, worker spawning, edits to existing files, installs, commits/pushes. Public repo files only, no personal data. Write only your report at /home/jun/git/spark-bench/artifacts/astra-perf-20260905/measurement-audit.REPORT.md. Aim <=20 minutes. Status success means audit complete, not optimization achieved.

## Done
Report status: success|blocked|failed, verified evidence with file/line citations, methodological risks, concise prioritized harness spec and test plan. Be adversarial about claimed speedups, not generic.
