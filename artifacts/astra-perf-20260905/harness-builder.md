# Harness hygiene builder — GLM bench suite

## Goal
Jun approved the full optimization campaign for tonight. Before any candidate experiment, the measurement stack must be fixed. Implement the prioritized harness changes from the independent audit. This is a coding task on /home/jun/git/spark-bench only — no cluster access, no benchmark runs, no ssh.

## Read first (in order)
- /home/jun/git/spark-bench/artifacts/astra-perf-20260905/measurement-audit.REPORT.md — tasks 3/4 contain the exact spec
- scripts/bench_c4_steady.py, scripts/bench_decode_full.py, scripts/run_cold_prefill_18888.py
- scripts/run_cold_prefill_18888.py's stream_chat (per-request cached_tokens + windowed metrics delta pattern to reuse)

## Deliverables (exact)
1. `scripts/bench_c4_steady.py` upgrade:
   - per-stream record: t_post, t_first, t_last, all inter-delta gaps, finish_reason, usage.prompt_tokens, usage.completion_tokens, usage.prompt_tokens_details.cached_tokens
   - new metric `steady_agg_tok_s` = Σct / (min(t_last) − max(t_first)) alongside existing e2e agg (rename existing number `e2e_agg_tok_s` in output, keep both)
   - TTFT per stream + ITL p50/p95/p99; tokens/bundle = ct/#deltas
   - windowed counter deltas per pass from /metrics: spec drafts/draft-tokens/accepted + per-position accepted, prefix hits/queries, gpu_cache_usage_perc, num_requests_running/waiting sampled at t0
   - assertions: exactly 4 successful streams, all finish_reason=="length", Σct == 4×max_tokens; violations mark pass invalid (record, don't crash)
   - CLI: --passes N (default 1, current behavior preserved), --cooldown S (default 60), --out DIR (required when passes>1) writing <name>-<UTC>-c4.json with O_EXCL; never overwrite
   - embed resolved config/env block (ASYNC_SCHEDULING, DFLASH_TOKENS, GLM53_MIXED_PREFILL_SMALL_OK, MAX_NUM_BATCHED_TOKENS from env) into the JSON
   - quiescence gate: assert num_requests_running==0 and waiting==0 at t0; post-window assert Δgeneration_tokens_total == Σct else mark pass invalid
2. `scripts/bench_decode_full.py` fixes: real ttft_s = t_first − t_post (remove hardcoded None); capture finish_reason per run; per-request cached_tokens toggle check replacing the global-counter block (L110–127); windowed spec counters per phase instead of end-only; --out param removing the L133 hardcoded dated path (default keeps old path ONLY with a loud deprecation warning; prefer requiring --out)
3. `scripts/run_cold_prefill_18888.py`: OUT_JSON becomes --out param, O_EXCL, timestamped default under /home/jun/glm-bench-results/
4. New `scripts/bench_mixed_guard.py`: run a C4 steady window (reuse bench_c4_steady functions via import or copy) and inject ONE front-salted ~16k-token cold prefill mid-window; report injected-request TTFT, C4 steady_agg retention, max per-stream inter-delta stall. Front-salt = unique random prefix so it cannot hit prefix cache.
5. New `scripts/sweep_driver.py`: per-config {export resolved env → relaunch via /home/jun/launch-glm53-exl3-tp4.sh ONLY when --relaunch passed (default: use current running serve) → poll /health + container log "async boot-shape warmup" completion (not fixed sleep) → quiescence asserts → warm-until-stable loop: repeated C4 passes until 3 consecutive pass steady_agg medians within 5% → 3 scored passes → collect docker `say "async=… k=… small_ok=…"` env line + per-rank nvidia-smi/dmesg OOM counts (forge/anvil/ember/flame via ssh, read-only) → enriched timestamped JSON}. Interleaved config ordering support via repeated invocations; append one line per phase to sweep.log. This driver must NOT hardcode any config list.
6. Fix existing committed bad data: leave historical files untouched (they are evidence), but add a `scripts/README-bench.md` documenting the four rulers, the known bugs fixed tonight, and the overwrite lesson.

## Hard constraints
- Only edit/add files under /home/jun/git/spark-bench/scripts/ (plus the new README there). Do not touch results/, artifacts/, README.md, launcher files, or anything on forge. No benchmark runs, no ssh, no docker, no installs (stdlib only — these harnesses are urllib-based, keep it that way).
- Keep the exact CODE prompt text, nonce-at-end placement, temp 0, thinking off, max_tokens 1600/400 conventions in bench_c4_steady.py so historical numbers stay comparable.
- Python 3.10+ stdlib only. Each script must pass `python3 -m py_compile`. bench_c4_steady.py --passes 1 with no --out must remain runnable exactly as before (single JSON to stdout) — additive changes only.
- Commit each logical change separately to main with git identity: `git -c user.name=Depths -c user.email=depths@eva-core commit` and trailer `Agent: depths`. Push after all green (`git push origin main`).

## Verification
- py_compile all touched scripts.
- Self-test without a server: run each script against a tiny local mock (python http.server returning canned /v1/chat/completions SSE + /metrics) or write a --self-test mode that validates parsing/formatting logic offline. At minimum prove O_EXCL behavior (second run to same path refuses), timestamped naming, JSON schema, and the invalid-pass flag logic.
- Report exact commit hashes.

## Report
Write /home/jun/git/spark-bench/artifacts/astra-perf-20260905/harness-builder.REPORT.md: status, commits, what verified, risks. First line: status: success|blocked|failed.
