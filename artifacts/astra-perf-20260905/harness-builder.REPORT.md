# harness-builder.REPORT — GLM bench suite hygiene campaign

status: success

All six deliverables implemented, verified offline (py_compile + --self-test
for every harness + full end-to-end runs against a stdlib mock serve), and
committed to main with the required identity/trailer and pushed. No cluster
access, no benchmark runs, no ssh, no docker, no installs; only files under
`scripts/` were added/modified.

## Commits (on origin/main)

| Commit | Deliverable |
|---|---|
| `c4a98f7` | 1. bench_c4_steady v2 |
| `d06ccf5` | 2. bench_decode_full v2 |
| `796e4c7` | 3. run_cold_prefill --out/O_EXCL (+ mock_serve.py verification utility) |
| `4b510d8` | 4. new bench_mixed_guard |
| `629c3f2` | 5. new sweep_driver |
| `ef051bb` | 6. scripts/README-bench.md |

Base: `4bc9128` (HEAD at campaign start). Pushed: `git push origin main`
(4bc9128..ef051bb). Diffstat vs base: 7 files, +1866/−89, all under `scripts/`.

## What changed, where

### scripts/bench_c4_steady.py (deliverable 1)
- Per-stream record: t_post, t_first, t_last, all inter-delta gaps,
  finish_reason, prompt_tokens/completion_tokens/cached_tokens, ttft_s,
  n_deltas, tokens_per_bundle, itl_ms {p50/p95/p99/max/mean}. Failed streams
  now return an error record instead of None (thread exceptions recorded).
- New `steady_agg_tok_s` = Σct/(min(t_last)−max(t_first)); old number renamed
  `e2e_agg_tok_s` (was client_wall_agg_tok_s); both reported.
- Windowed /metrics deltas per pass: spec drafts/draft-tokens/accepted,
  per-position accepted, prefix hits/queries; gpu_cache_usage_perc and
  num_requests_running/waiting sampled at t0; gen-token reconciliation.
- Validity gates (recorded, never crash): exactly 4 streams, all
  finish_reason=="length", Σct==4×max_tokens, t0 quiescence, post-window
  Δgeneration_tokens_total==Σct. Evaluation factored into a pure
  `evaluate_pass()` so all gate logic is offline-testable.
- CLI: --passes (default 1 = old single-JSON-to-stdout behavior), --cooldown
  (default 60), --out DIR (required when passes>1; `<name>-<UTC>-c4.json`
  with O_EXCL), --name, --base, --self-test. Resolved env block
  (ASYNC_SCHEDULING, DFLASH_TOKENS, GLM53_MIXED_PREFILL_SMALL_OK,
  MAX_NUM_BATCHED_TOKENS) + prompt_sha256 embedded in every artifact.
- Frozen conventions preserved exactly: CODE prompt text, end-nonce, temp 0,
  thinking off, 1600/200 tokens, warmup round.

### scripts/bench_decode_full.py (deliverable 2)
- Real ttft_s = t_first − t_post (hardcoded None removed).
- finish_reason captured per run (length vs EOS distinguishable; C1 cells
  print finish distribution).
- Thinking-toggle check replaced (old L110–127 global-counter block): now
  per-request usage.prompt_tokens_details.cached_tokens on streamed
  requests; reports cold/toggle prompt_tokens, cached_tokens, ttft, ratio.
- Spec counters windowed per phase (warmup, each of 8 C1 cells, C4, toggle)
  incl. per-position acceptance; boot-cumulative end snapshot kept labeled.
- --runs N (default 3 = historical) with mean/stdev alongside median.
- --out PATH with O_EXCL; without --out the old dated path is used only
  with a loud stderr deprecation warning, and a second run to that path
  refuses (exit 2).

### scripts/run_cold_prefill_18888.py (deliverable 3)
- Hardcoded dated OUT_JSON removed; --out PATH (O_EXCL) or timestamped
  default /home/jun/glm-bench-results/cold-prefill-<UTC>.json; --base param.
  All existing ladder/protocol logic untouched.

### scripts/bench_mixed_guard.py (new, deliverable 4)
- Reuses bench_c4_steady functions (import) for the C4 steady window; injects
  ONE ~16k-token front-salted cold prefill mid-window (calibrated via
  /tokenize using run_cold_prefill's calibrate/stream_chat; unique random
  prefix so it cannot hit the prefix cache — mock proves cached_tokens=0).
- Reports injected TTFT/prompt_tokens/cached_tokens/finish_reason, C4
  steady_agg retention (guard/baseline), max per-stream inter-delta stall
  vs baseline. Guard-pass gen-token reconciliation includes the injected
  request's tokens. --out with O_EXCL, --self-test.

### scripts/sweep_driver.py (new, deliverable 5)
- Per-config pipeline: resolved env (base env + config overrides, recorded
  in artifact) → relaunch via launcher ONLY with --relaunch (default: reuse
  current serve) → poll /health → poll async boot-shape warmup completion
  (case-insensitive POSIX-ERE regex on the warmup log; fallback =
  log-quiet+healthy, criterion recorded — never a fixed 180 s sleep) →
  quiescence asserts → warm-until-stable (repeated C4 passes until 3
  consecutive steady_agg within --stability-tol 5%, capped at
  --max-warm-passes; warmup curve recorded as evidence) → 3 scored passes →
  docker `say "async=… k=… small_ok=…"` env-line capture + per-rank
  nvidia-smi/dmesg OOM counts via read-only ssh → enriched
  `<name>-<UTC>-sweep.json` with O_EXCL.
- NO hardcoded config list: --config NAME[:K=V,...] repeatable and/or
  --configs-file FILE.json; interleaved ordering = pass order; repeated
  invocations append one line per phase to sweep.log.

### scripts/README-bench.md (deliverable 6)
- Documents the four rulers + driver, named aggregate metrics, frozen
  conventions, the four bug classes fixed tonight, the overwrite lesson
  (O_EXCL everywhere; historical files are evidence), and the warmth/acceptance
  protocol. Historical files untouched.

## What was verified (real commands)

- `python3 -m py_compile` on all six scripts — clean (Python 3.14.7).
- `--self-test` on bench_c4_steady (23 checks), bench_decode_full (7),
  bench_mixed_guard (7), sweep_driver (17) — all PASS. These cover metrics
  parsing (incl. per-position), counter deltas, percentile math,
  steady/e2e agg computation, all five invalid-pass flags (early-EOS
  sum_ct, finish_reason, quiescence, third-party gen-delta, 3-of-4 streams),
  O_EXCL refusal, timestamped naming, config/env parsing, stability
  logic, log-line format, and no-hardcoded-configs check.
- End-to-end against `scripts/mock_serve.py` (stdlib-only canned vLLM serve):
  - bench_c4_steady single pass (valid, steady/e2e split, TTFT/ITL, cached
    tokens, quiescence, windowed spec deltas); 2-pass run with --out;
    `--passes 2` without --out errors as specified.
  - bench_decode_full full run (C1 cells with mean±sd + finish reasons,
    C4, per-request cached_tokens toggle check, per-phase spec deltas);
    no---out run emits the loud deprecation warning and writes the old
    path; second run refuses (exit 2).
  - run_cold_prefill full ladder (8k/16k/100k/300k + APC follow-up;
    calibrated tokenize; cached_tokens=0 on cold rungs); same-path rerun
    refuses.
  - bench_mixed_guard full run (retention 0.999 on mock; injected
    cached_tokens=0 proving front-salt cold; guard pass valid with
    injected tokens in the gen reconciliation).
  - sweep_driver two-config run (legA/legB with env overrides; warmup regex
    criterion; warm-until-stable converged at pass 3; scored passes; sweep.log
    phase lines; telemetry graceful-failure recording; two runs → two
    distinct O_EXCL files).
- Constraint compliance: `git diff 4bc9128..HEAD --stat` shows only the
  7 files under scripts/; results/, README.md, launcher files untouched; no
  network beyond `git push`; mock runs on 127.0.0.1 only.

## Risks / residual

- The warmup-done regex is permissive because the actual
  boot-shape-warmup.sh completion wording is not in this repo (it lives on
  forge at /home/jun/glm53-exl3-recipe/scripts/). Default matches
  `warmup.*(done|complete|finished|ok|success)` case-insensitively; the
  log-quiet+healthy fallback (120 s) covers a different wording, and the
  criterion that fired is recorded per config. First real run should confirm
  which criterion fires and tighten `--warmup-done-regex` if needed.
- Per-position spec counters: only positions present in /metrics are
  diffed (live serve showed positions 0–6); absent positions read as 0-delta.
- bench_decode_full keeps the old dated default path (with loud warning) per
  the builder spec — a careless future run without --out still targets that
  path, though O_EXCL now prevents overwriting whatever is there.
- bench_c4_steady output renamed `client_wall_agg_tok_s` → `e2e_agg_tok_s`
  (explicitly requested); any external consumer of the old key must be
  updated. The 2026-09-04 sweep wrapper (uncommitted) would parse the old key.
- mock_serve.py is a verification utility, not a load simulator — its numbers
  are meaningless; only harness mechanics were validated against it.
- sweep_driver's ssh/docker/launcher paths were exercised only in
  graceful-failure mode locally (no cluster access tonight); the command
  shapes follow launcher.snapshot.sh (container `glm53-exl3`, warmup log
  /tmp/glm53-exl3-warmup.log, say-line `async=… small_ok=…`) but were not
  proven against the live cluster.
- artifacts/ remains untracked in git (as before); this report is the only
  new file there.
