# GLM bench harnesses — rulers, conventions, and lessons

This documents the measurement harnesses in `scripts/` for the GLM 5.3 Flash
EXL3 TP4 serve on `forge:18888`. It exists because the 2026-09-05 measurement
audit (artifacts/astra-perf-20260905/measurement-audit.REPORT.md) found the
harnesses recording unlabeled/incomparable numbers, silently dropping bad
passes, and overwriting evidence.

## The four rulers (plus the driver)

Never mix numbers from different rulers in one comparison.

| Ruler | Script | Measures | Regime |
|---|---|---|---|
| **C4 steady decode** | `bench_c4_steady.py` | 4 concurrent 1600-token code streams | warm prefix cache (shared prefix), pure decode |
| **C1 decode suite** | `bench_decode_full.py` | 1-stream tok/s × category × thinking on/off + a short C4 cell | mixed; the C4 cell is a *low* short-window ruler — do not compare with C4 steady |
| **Cold prefill ladder** | `run_cold_prefill_18888.py` | TTFT/prefill tok/s at ~8k/16k/100k/300k prompt sizes | true-cold via front-salted unique prompts (no cache flushes) |
| **Mixed-prefill guard** | `bench_mixed_guard.py` | C4 steady + ONE ~16k front-salted cold prefill mid-window; reports injected TTFT, steady-agg retention, max per-stream stall | the ruler that can see what decode-floor / SMALL_OK / long-prefill-threshold *protect* |
| **Sweep driver** | `sweep_driver.py` | orchestrates configs: resolved env → (relaunch or reuse) → health → warmup-complete poll → quiescence → warm-until-stable → scored passes → telemetry | must be used for any config comparison |

### Named aggregate numbers (C4 steady)

- `steady_agg_tok_s` = Σ completion_tokens / (min(t_last) − max(t_first)) —
  the all-4-decoding overlap window. **This is the primary metric.**
- `e2e_agg_tok_s` = Σ completion_tokens / (window from before thread start
  to after join) — includes connect, prefill, stagger, drain. This is the
  historical number (was `client_wall_agg_tok_s`); it reads ~5% lower.
- `per_stream_tok_s` = (ct−1)/(t_last−t_first) per stream — decode-only mean,
  TTFT excluded.
- `server_gen_rate_tok_s` is a quiescence assertion (Δgeneration counter over
  the same window), not an independent throughput measurement.

## Frozen conventions (do not change — voids all cross-day comparisons)

- Exact CODE prompt text (hash recorded in every artifact's `config.prompt_sha256`).
- Nonce appended at the **end** of the prompt: the shared prefix stays
  prefix-cache warm on purpose. Cold prompts instead use a **front-salt**
  (unique random prefix, e.g. `run_cold_prefill_18888` / `bench_mixed_guard`)
  so the prefix cache cannot be warm; `cached_tokens` proves the regime per
  request — we never flush caches on the shared serve.
- `temperature: 0`, `enable_thinking: false` via `chat_template_kwargs`,
  `max_tokens` 1600 (measured) / 200 (warmup round) for C4 steady.
- Token counting is **usage-based** (`stream_options.include_usage`), never
  SSE-chunk counting (spec-decode bundles ~8 tokens per delta).
- Quiescence before every measured window: `num_requests_running == 0` and
  `num_requests_waiting == 0`; post-window, Δ`generation_tokens_total` must
  equal Σ completion_tokens, else the pass is flagged invalid.
- Pass validity gates (recorded, never crash the run): exactly 4 successful
  streams, all `finish_reason == "length"`, Σct == 4×max_tokens.

## Known bugs fixed on 2026-09-05 (harness-builder campaign)

1. **bench_c4_steady.py**: TTFT/ITL/finish_reason/cached_tokens never
   recorded; two unlabeled rulers side by side; early-EOS streams silently
   undercounted (the sweep baseline-C `tokens: 6235` bias); failed streams
   dropped without an error field; no pass validity gates; no resolved-env
   block in artifacts. All fixed (v2), protocol frozen.
2. **bench_decode_full.py**: `ttft_s` was hardcoded `None` (dead in every
   artifact); `finish_reason` never captured (EOS vs length
   indistinguishable); the thinking-toggle check used global prefix-cache
   counters that read 0.0 hits in both committed runs while a 96.6% claim was
   published from an uncommitted harness — replaced with per-request
   `usage.prompt_tokens_details.cached_tokens`; spec counters were
   boot-cumulative end-only — now windowed per phase (incl. per-position
   acceptance); output path hardcoded to a 2026-09-02 date.
3. **run_cold_prefill_18888.py**: hardcoded dated `OUT_JSON` — this exact
   defect destroyed the pre-E2 "before" evidence (the pre and post files were
   byte-identical; the "before" data survives only as README prose).
4. **Sweep driver**: was not committed at all; sweep artifacts did not record
   the resolved serve env (launcher defaults ≠ standing cycle-C env); the
   container's `say "async=… k=… small_ok=…"` env line lived only in docker
   logs; warmup was a fixed 180 s sleep. Now committed with poll-based
   warmup gating, quiescence asserts, and warm-until-stable.

## The overwrite lesson (mandatory reading)

Two rulers wrote to hardcoded dated paths; rerunning them silently destroyed
the previous run's evidence, and it already fired once (item 3 above).
**Every harness now writes with O_EXCL and refuses to overwrite** — if you
see `REFUSED: ... already exists`, do not delete the old file; use a fresh
timestamped path (`--out`) and let the old artifact stand as evidence.
Historical files under `results/` are evidence and are never touched.

## Offline verification

`python3 scripts/mock_serve.py` is a stdlib-only canned vLLM serve (SSE chat
completions with advancing /metrics counters, /tokenize, /health). Every
harness passes `--self-test` (pure offline logic) and was additionally
verified end-to-end against the mock — no cluster, ssh, or docker needed.

## Warmth protocol (the F5.2 lesson)

Cold first-run-after-boot numbers drifted +24.6% within a single boot on
09-02; the 09-04 sweep compared single cold runs and mistook drift for patch
effects. Any config comparison must: wait for the async boot-shape warmup to
actually complete (poll, not fixed sleep), then run the C4 ruler repeatedly
until 3 consecutive pass `steady_agg` values agree within 5%, and only then
take scored passes. Acceptance for adopting a config change: B beats A
(warm steady-agg median) by > max(2×A-spread, 5%) **and** the mixed-prefill
guard does not regress **and** correctness guards pass. A +4–5% "win" is
inside demonstrated regime noise — not adoptable without repeats.
