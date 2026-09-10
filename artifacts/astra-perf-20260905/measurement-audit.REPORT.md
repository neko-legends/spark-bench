# measurement-audit.REPORT — independent measurement audit, GLM C4 throughput

status: success

Read-only audit completed from public repo files at HEAD 4bc9128. No ssh, no
benchmark traffic, no workers, no edits to existing files, no installs, no
commits. Only this report was written. Everything below was verified with
local commands (read/diff/md5sum/git log/grep/arithmetic), not assumed.

## Files read in full

- README.md (GLM 5.3 Flash section, esp. lines 16, 114–121, 159, 282–296)
- scripts/bench_c4_steady.py, scripts/bench_decode_full.py,
  scripts/run_cold_prefill_18888.py (referenced by README as the prefill ruler)
- results/verify-C-c4-2026-09-03.json, results/verify-C-decode-2026-09-03.json,
  results/verify-C-prefill-2026-09-03.json
- results/c4-sweep-20260904-0030/: SUMMARY.md, sweep.log, all 6 config JSONs
  and all 6 *.raw.json
- Aug-28 comparison evidence: README.md:282/289–296, commit f413842 (message +
  added files), results/bench_decode_2026-09-02.json,
  results/bench_c4_toggle_2026-09-02.json, results/ab-cycleC-*-2026-09-02.json
- Campaign context (same artifacts dir): astra-investigation.md,
  live-audit.txt, launcher.snapshot.sh

---

## Task 1 — Harness/evidence audit (bugs, with file/line/data evidence)

### F1. The "253 tok/s Aug-28 C4 aggregate" was never measured. It is 4× a C1 number.

This is the single most important finding: the regression baseline does not exist.

- README.md:282 shows its own derivation inline:
  `| EXL3 TP4 (think off, Aug 28 config) | 64.5 | 100.9 | 77.8 | 23.1 | 253† (4×63.3) | 1M |`
  — 4 × 63.3 = 253.2. That is single-stream C1 code tok/s multiplied by 4,
  i.e. an extrapolation assuming **zero concurrency degradation**.
- README.md:289–290 then claims "the Aug 28 serve **measured** 253 tok/s
  aggregate on 4× code streams … **with the same harness**". Both halves are
  false: (a) it contradicts :282's own `(4×63.3)`; (b) `bench_c4_steady.py`
  did not exist on Aug 28 — `git log --follow scripts/bench_c4_steady.py`
  shows it was first committed 2026-09-02 17:27 (f413842).
- No Aug-28 GLM raw result file has ever existed in git history
  (`git log --all --name-only -- results/`: zero files matching 08-26…08-29
  for the GLM lane; August result files are all DeepSeek lane).
- Commit f413842's message ("C4 aggregate 88–112 vs 150–253 Aug") cites "150"
  with no surviving artifact either.
- The extrapolation class is known-bad on this very cluster: DeepSeek lane
  measured C4 agg 182 vs 4×C1 = 544 (README DeepSeek section) — the same
  4×C1 method overestimates by ~3×. On today's GLM serve, 4×C1-code-off
  (58.7, verify-C-decode) = 234.8 vs measured agg 128.9 (ratio 1.82).
- What *is* supported: C1 parity across the two serves (Aug-28 code-off 64.5
  vs 09-03 58.7, inside the README's own ±5 noise band, README:118). There is
  no measured single-stream regression, and no measured Aug-28 C4 number at
  all. "253 → 128.9" compares a perfect-scaling extrapolation against a
  measured end-to-end aggregate; the ~49% "regression" magnitude is an
  artifact of ruler mismatch, not an established fact.

### F2. bench_c4_steady.py — formula and protocol defects

- **Two different rulers reported side by side, unlabeled.** Per-stream
  `(ct−1)/(t_last−t_first)` (L41–42) is a decode-only mean rate (TTFT
  excluded, first-delta→last-delta). Aggregate `sum(ct)/(t1−t0)` (L56–57)
  uses a window opened *before thread start* and closed *after join* — it
  includes connect, prefill, stream stagger, and drain. verify-C-c4 shows the
  mismatch: per-stream mean ×4 = 135.4 vs aggregate 128.9 (−4.8%). Neither
  number is "4-stream steady decode"; they must be named and separated.
- **server_gen_rate is not an independent check.** `(g1−g0)/(t1−t0)` over the
  same window (L15–20, L54–57) uses a global counter — any third-party
  traffic inflates it. It equals client wall to 0.1 in all 7 artifacts
  (128.9/128.9 and all 6 sweep pairs), which is good quiescence evidence, but
  it adds no independent information (same numerator in practice). Keep it as
  a quiescence *assertion*, not a second metric.
- **Token counting is correct**: usage-based via
  `stream_options:{"include_usage":true}` (L27–29, L35, L41), not SSE chunk
  counting — avoids the ~8× spec-decode undercount documented in the README
  SGLang gotcha #3. Timing counts all three delta keys
  (content/reasoning/reasoning_content, L37). This part is sound.
- **Warmup and cache regime are implicit.** Warm round is 4×200 tokens of the
  same CODE prompt (L44–48); the nonce is appended at the *end*
  (`prompt + " nonce=" + uuid4().hex`, L27–28), so the shared prompt prefix
  is cache-warm for the measured round. Fine for steady decode, but it means
  the published aggregate assumes warm prefix cache and near-zero prefill —
  and identical prompts at temp 0 make the 4 streams produce identical text
  (correlated drafter acceptance, not 4 independent samples). Nothing in the
  output records this regime.
- **TTFT is never measured** (t_first exists but no t_post is kept); no
  inter-token latency distribution; no finish_reason; no per-stream
  timestamps → stream overlap ("were all 4 really concurrent?") is unverifiable.
- **EOS/length finishes untracked, and it already bit the sweep.**
  baseline-C.json has `tokens: 6235` (< 4×1600): one stream finished early
  (~1435 tok). Aggregate silently undercounts ~2.6% (6235/58.6 = 106.4; at
  equal rates 6400/58.6 ≈ 109.2). All other configs produced exactly 6400.
  Nothing flags or corrects this; the reference point of the whole sweep is
  biased low.
- **Failed/missing runs degrade silently.** `stream_once` returns None on
  missing usage/ct<2 (L42); `per`/sums filter `if r` (L57–59). A thread
  exception leaves outs[i]=None (Python doesn't propagate thread exceptions
  through join) → a 3-stream aggregate divided by a 4-stream window, no error
  field. Timeout is a bare urlopen timeout=900 (L11–13).

### F3. bench_decode_full.py — defects

- **`"ttft_s": None` is hardcoded** (L58) — the field is dead in every
  artifact; TTFT has never been captured by this harness.
- **Warmup is irrelevant to what it measures**: 3 × 32-token requests on an
  80-char truncated prompt (L81–83). Nothing warms the 400-token C1 regime or
  the batch-4 C4 shape before the C4 section.
- **Its C4 section is a systematically low ruler**: single pass of 4×400
  tokens, ~15–18 s window (L96–108), dominated by batch-formation transient.
  Same night, same config: this harness says C4 = 107.6 (per-stream
  27.8–29.6, verify-C-decode) while bench_c4_steady says 128.9 (per-stream
  33.1–36.2, verify-C-c4). Two "C4 aggregate" numbers 20% apart from the
  verified boot; the README headlines only 128.9. Short-window C4
  understates steady aggregate — never mix the two rulers in one comparison.
- **C1 cells: n=3, 400 tokens, sequential order** (categories × thinking,
  no interleaving). Observed within-cell spread up to 43% (code_thinkon
  41.6–59.5, verify-C-decode). Medians of 3 printed to 0.1 = false precision.
  math_thinkoff run 3 EOS'd at 239/400 tokens and was silently included —
  finish_reason is never captured, so length-vs-EOS is indistinguishable.
- **Spec counters are boot-cumulative, sampled once at the end** (L60–67,
  L131) → the commit-message claim "DFlash2 C1 acceptance ~52%"
  (9471/18417 = 51.4% in verify-C-decode) actually covers boot warmup + all
  C1 + C4; it is not phase-attributable. Per-position acceptance counters
  exist on the live serve (live-audit.txt, positions 0–6) and are ignored.
- **Inline thinking-toggle prefix check reads 0.0 in BOTH committed runs**
  (bench_decode_2026-09-02.json: toggle_hits 0 / queries 1240;
  verify-C-decode-2026-09-03.json: 0 / 1240) while commit f413842's message
  claims "96.6% hit" and README:159 claims 97%. The 0.966 lives only in
  bench_c4_toggle_2026-09-02.json (28672/29696), produced by a *different,
  uncommitted* harness. The cycle-C "verified" artifact therefore contradicts
  the published 97% claim, and the discrepancy is unresolved from repo data.
  Counter-name parsing is not the cause (live metrics confirm
  `vllm:prefix_cache_hits_total{...}` matches the startswith check,
  live-audit.txt). Fix: record per-request
  `usage.prompt_tokens_details.cached_tokens` — run_cold_prefill_18888.py
  already implements exactly this (its `stream_chat` return dict) — instead of
  global counters around non-streaming calls.
- **Hardcoded dated output** (L133): every run writes
  `/home/jun/glm-bench-results/bench_decode_2026-09-02.json` regardless of
  date → each future run destroys the previous run's evidence.

### F4. The overwrite failure mode already fired once — verified

run_cold_prefill_18888.py hardcodes
`OUT_JSON = Path("/home/jun/glm-bench-results/cold-prefill-baseline-2026-09-02-pre-e2.json")`
(L22). Verified consequence: `diff` of
results/cold-prefill-baseline-2026-09-02-pre-e2.json vs
results/cold-prefill-2026-09-02-post-e2.json → byte-identical (both md5
c29aeb6be1f779644ef6e62e07e2141a). The pre-E2 "before" data survives only as
README prose — exactly as the README's own data-hygiene note admits. Both
rulers (decode L133, prefill L22) carry the same defect. Otherwise the
prefill harness is the methodological best-in-repo: real tokenizer calibration
via /tokenize, finish_reason, cached_tokens, TTFT from POST, per-request
metrics deltas, front-salted prompts for true-cold.

### F5. Other comparability breaks (old vs new)

- The 09-04 chat-template parity bench quoted in the README ("structured
  92.8/96.9, math 67.6/72.6 …") has **no committed raw file** (grep of
  results/ finds nothing) — same evidence-gap class as the 253 claim.
- verify-C-prefill-2026-09-03.json is internally consistent (windowed
  metrics, finish_reason), but the README's "~8k rung is JIT-warmup noise"
  exclusion (09-02 entry) documents that first-after-boot rungs are
  unreliable for prefill — the identical lesson the C4 sweep violated
  (below).
- Sweep artifacts do not record the **resolved** serve env. The launcher
  snapshot defaults are `ASYNC_SCHEDULING:-0` and
  `GLM53_MIXED_PREFILL_SMALL_OK:-0` (launcher.snapshot.sh) — NOT the
  documented standing cycle-C env (README: ASYNC_SCHEDULING=1, SMALL_OK=2048).
  baseline-C.json records `"env": ""`; whether the sweep wrapper exported
  cycle-C env globally is unverifiable from the repo. The inner script's
  `say "async=… k=… small_ok=…"` line exists only in docker logs and was not
  captured into artifacts. The sweep driver script itself is not committed
  (no file in scripts/ contains the sweep logic).

---

## Task 2 — The causal claim ("removing any patch gains ~25% ⇒ regression shared across the patch set") is UNPROVEN

SUMMARY.md:20–24 draws a causal conclusion from a design that cannot support
it. Concretely:

1. **n=1 per config, first-run-after-boot, by the summary's own admission**
   (SUMMARY.md:16–17 "cold-cache regime"). No repeats, no interleaving, no
   closing baseline (A/B/A) — the sweep ran strictly in fixed order
   00:48→02:28 (sweep.log).
2. **Same-config variance of the claimed effect size is demonstrated in-repo.**
   Config C alone measured 106.4 (sweep cold), 117.0 (09-02 original,
   ab-cycleC-c4), 128.9 (09-03 warm verified): a 21% spread with **zero**
   config change. Even sharper: on 09-02, the *same boot, minutes apart*, C4
   aggregate went 89.8 → 98.2 → 111.9 across successive passes
   (bench_decode_2026-09-02.json + bench_c4_toggle_2026-09-02.json) = +24.6%
   intra-boot drift — the exact magnitude the sweep attributes to patch
   removal.
3. **Recomputed against the warm baseline, the "gains" mostly vanish**:
   vs cold baseline 106.4: async-off +8.1%, mnbt-1024 +12.4%,
   no-drafter-group +26.3%, no-spinwait +23.9%, no-decode-floor +27.6%.
   vs the *warm* verified 128.9 of the identical config: −10.8%, −7.2%,
   **+4.3%, +2.2%, +5.4%**. A warmed no-decode-floor boot might land at
   128.9–160; nobody measured it. async-off and mnbt-1024 are inside
   demonstrated same-config noise on any reading.
4. **Time-order confound**: aggregate is near-monotonic in run order
   (Spearman ρ = 0.943 over the 6 configs). Triton/TileLang caches persist
   across boots (launcher mounts $VLLM_CACHE_HOST/triton,tilelang), boot-shape
   warmup is *asynchronous* (launcher: setsid nohup after /health) while the
   sweep waited a fixed 180 s (sweep.log) that may not cover it, and the
   preflight drops page cache per boot. Later boots being systematically
   warmer is indistinguishable from "removing patches helps" in this design.
5. **The reference point is biased low**: baseline-C lost ~165 tokens to an
   early EOS (tokens 6235 vs 6400) → ~2.6% undercount (≈109.2 corrected),
   inflating every delta.
6. **Toggles are not single-change in effect**: mnbt-1024 silently breaks the
   assumptions of two other standing knobs (LONG_PREFILL_TOKEN_THRESHOLD=1792
   and SMALL_OK=2048 both exceed MNBT=1024), so that arm tests a different
   scheduler regime, not one knob.
7. **The ruler cannot see what the removed patches protect.** decode-floor
   (`GLM53_MIXED_PREFILL_CHUNK=skip`) and the mixed-prefill guards exist to
   stop big prefills from collapsing a decoding peer (README 08-28: peer
   ~55→~5 tok/s; 09-02: first stream monopolizes decode). A pure-C4
   same-shape ruler contains **no prefill traffic**, so by construction those
   patches can only show cost, never benefit, on this ruler. Removing them
   "wins" trivially. The sweep measured none of the mixed-prefill capability
   they were adopted for — the causal ranking is not just noisy, it is
   measuring the wrong workload for three of the six arms.

**What the data does support (honest statement):** "On a cold,
first-run-after-boot, pure-C4 ruler, single boots with drafter-group,
spinwait, or decode-floor removed each landed ~132–136 agg vs a same-night
cold baseline of 106.4 (itself ~2.6% undercounted); this is
hypothesis-generating only." It does **not** support any ranking among the
patches, does not support "shared across the patch set", and does not support
any comparison to 253 (which was never measured) or to 128.9 (warm ruler,
different regime).

---

## Task 3 — Minimal safe benchmark protocol (bounded, no cache flushes)

**Quiescence (before every measured window)**
- kv-catchup sidecar stopped (the sweep did this — keep it, record it).
- Assert `vllm:num_requests_running == 0` and `num_requests_waiting == 0`
  (both exist, live-audit.txt) immediately before t0; abort/flag otherwise.
- Post-window assertion: `Δgeneration_tokens_total == Σ completion_tokens`;
  mismatch ⇒ third-party traffic ⇒ discard the pass. (The data shows this
  held historically — make it an explicit gate.)

**Warmth (the lesson of F5.2)**
- Per boot: wait for the async boot-shape warmup to actually finish (poll its
  log/completion, not a fixed 180 s), then run the C4 ruler repeatedly
  (≥3 passes, ≥60 s apart) until 3 consecutive pass medians are within 5%.
  Only then start measured passes. Record every warm pass — the warmup curve
  is itself evidence (it quantifies the cold regime instead of hiding it).

**Per-measured-pass content (C4 ruler)**
- 4 concurrent streams, matched prompts, thinking off, temp 0, max_tokens
  1600, nonce at prompt end (existing convention — document why: steady-decode
  regime deliberately rides the prefix cache).
- Record per stream: t_post, t_first_delta, t_last_delta, all inter-delta
  gaps, finish_reason, usage.prompt_tokens, usage.completion_tokens,
  usage.prompt_tokens_details.cached_tokens.
- Report four distinct numbers, named:
  1. `gen_tok_s_per_stream` = (ct−1)/(t_last−t_first) (existing formula, keep)
  2. `steady_agg_tok_s` = Σct / (min(t_last) − max(t_first)) — the all-4-
     decoding overlap window (computable once timestamps are recorded)
  3. `e2e_agg_tok_s` = Σct / (max(t_last) − min(t_post)) — today's number,
     relabeled
  4. TTFT per stream + ITL p50/p95/p99 (from recorded gaps; note spec-decode
     bundling: also report tokens/bundle = ct/#deltas)
- Gate: all 4 finish_reason == "length" and Σct == 4×max_tokens, else flag
  the pass invalid and repeat (fixes the baseline-C 6235 silent bias).
- Windowed counter deltas per pass: spec drafts/draft-tokens/accepted +
  per-position accepted, prefix hits/queries, gpu_cache_usage_perc (all
  already in /metrics; the prefill harness's delta pattern is the template).

**Coverage per config (bounded cost)**
- C4 steady: 3 measured passes ≈ 3×60 s + cooldowns ≈ 5 min bench time/boot.
- C1: 4 categories × thinking{on,off} × n=5 × 400 tok ≈ 8 min (report
  mean±sd, not median-of-3).
- Structured/code/prose are the decode discriminators (math optional;
  structured is the xgrammar/FSM correctness canary).
- Mixed-prefill guard (new, small, the missing ruler): during a C4 steady
  window, inject one ~16k cold (front-salted) prefill; report the injected
  request's TTFT, the C4 steady-agg retention, and max per-stream inter-delta
  stall. This is the ruler that gives decode-floor/SMALL_OK/long-prefill-
  threshold their fair trial.
- Cold prefill ladder only when a change touches prefill: 16k + 100k rungs
  (~15 s + ~70 s + calibration); skip 300k unless the change targets it.
- Telemetry per pass, all 4 ranks: nvidia-smi clocks/temp/mem, dmesg OOM
  counts before/after (the sweep wrapper already collects these — keep),
  plus the container's resolved-env `say "async=… k=… small_ok=…"` line
  captured from docker logs into the artifact.
- **No cache flushes** on the live shared serve (constraint + it would
  perturb the production prefix cache). Cold is achieved with front-salted
  unique prompts (run_cold_prefill convention), warm-steady with shared
  prefixes; `cached_tokens` proves the regime per request instead of
  flushing to force it.

**Cost bound:** boot 12–21 min (sweep.log boot_s 688–1255 s) + ~15–20 min
bench per boot ⇒ one config ≈ 30–40 min; a full A/B/A with 2 boots/leg
≈ 3–4 h wall. A single warm re-baseline of config C (the SUMMARY's own
"next lever") is 1 boot ≈ 35 min.

**Overwrite prevention (mandatory, F3/F4):**
- All three harnesses take `--out DIR` and write
  `<name>-<UTC timestamp>-<config>.json` opened with O_EXCL — refuse to
  overwrite, never hardcode a date. Kill bench_decode_full.py L133 and
  run_cold_prefill_18888.py L22 fixed paths.

---

## Task 4 — Next A/B/A criteria, guards, and exact minimal harness changes

**Design**
- Legs: A (current cycle-C env, explicitly exported — never rely on launcher
  defaults, which disagree with the standing config) → B (candidate) → A′.
  ≥2 boots per leg; interleave boots A,B,A,B where downtime allows; each boot
  runs the warm-until-stable loop, then 3 measured passes.
- **Variance thresholds:** within-boot pass spread ≤5%; same-config
  between-boot spread (A vs A′, warm) ≤5%; if A vs A′ differs by >5%, the
  session is invalid (thermal/time drift) — repeat. These thresholds are set
  by the measured facts: intra-boot drift reached +24.6% cold, but warm
  verified runs were tight (verify-C per-stream 33.1–36.2 ≈ ±4.5%).
- **Acceptance:** B beats A on the pre-registered primary metric (warm
  steady_agg_tok_s median) by > max(2×A-spread, 5%), AND the mixed-prefill
  guard does not regress, AND all correctness guards pass. A "win" of the
  size seen in the sweep (+4–5% vs warm) is *not* adoptable without repeats —
  it is inside regime noise.

**Correctness/capability guards (every leg)**
- Structured-output FSM probe (xgrammar termination backport regression),
  thinking on/off render check (off ⇒ zero reasoning tokens in usage),
  tool-call/tool-result render probe (09-04 template), finish_reason
  distribution sanity, spec acceptance per phase (a drafter-acceptance
  collapse is a silent capability regression even if tok/s rises).
- Mixed-prefill guard (Task 3): injected-16k TTFT and C4 retention within
  −5% of A. This is the guard that protects the *reason* decode-floor and
  SMALL_OK exist; no patch-removal proposal may skip it.
- C1 suite within ±5% of A per category; cold prefill 16k/100k within −5%
  (protects the E2 2× prefill win from being traded away invisibly).
- OOM counters zero during all measured windows; per-rank mem/clock telemetry
  archived with the artifact.

**Exact minimal harness changes for a builder (prioritized)**
1. `scripts/bench_c4_steady.py`: record per-stream
   t_post/t_first/t_last/finish_reason/prompt_tokens/cached_tokens; add
   overlap-window `steady_agg_tok_s`; add TTFT + ITL percentiles; add
   windowed spec/prefix/cache-usage counter deltas; token/finish assertions
   with pass-invalid flag; `--passes N --cooldown S` loop; `--out` with
   O_EXCL timestamped filenames; embed resolved-config/env block.
2. `scripts/bench_decode_full.py`: compute real `ttft_s` (t_first − t_post)
   instead of hardcoded None (L58); capture finish_reason; replace the
   global-counter toggle check (L110–127) with per-request `cached_tokens`;
   windowed spec counters per phase instead of end-only (L131); n≥5 with
   mean±sd; parameterize output path (remove L133 hardcode).
3. `scripts/run_cold_prefill_18888.py`: parameterize OUT_JSON (remove L22
   hardcode), O_EXCL.
4. New committed sweep driver (currently missing from the repo):
   per-config {export full resolved env → boot → health → wait for async
   boot-shape warmup completion (poll, not fixed 180 s) → quiescence asserts
   → warm-until-stable → 3 passes → telemetry + docker `say` env line →
   enriched JSON}; interleaved config ordering; appends to sweep.log.
5. New mixed-prefill guard harness (small): C4 steady + one front-salted ~16k
   arrival mid-window; outputs injected TTFT, steady-agg retention, max
   per-stream stall.

## Methodological risks (residual)

- Everything here is artifact-based; per constraints I made no live requests,
  so live metric semantics (e.g. exact counter update timing under
  --async-scheduling) are assumed from the recorded exact client/server
  agreement, which is strong but indirect evidence.
- The toggle-check contradiction (0.0 in both committed runs vs 0.966
  claimed/uncommitted harness) is unresolved from repo data; my recommended
  fix (per-request cached_tokens) makes it decidable in one run.
- The 09-02/09-04 harnesses live partly outside the repo
  (/home/jun/glm-bench-results/, boot-shape-warmup.sh, sweep driver) —
  repo-only reproducibility is currently impossible; change #4 fixes this.
- Host-level state may be an unmeasured variance source: live-audit.txt
  shows forge at MemAvailable 5.2 GiB with 4.4 GiB swap used; whether the
  GPU clock-lock service is active on the GLM lane is undocumented. Both
  should be recorded per boot by the new driver.
- If the builder changes max_tokens, prompt text, or nonce placement, all
  cross-day comparisons void; freeze the ruler text and version it in the
  artifact.

## Constraint compliance

No ssh / no live requests / no workers / no installs / no commits or pushes;
no existing file modified (verified: this report is the only new file);
public repo files only; no personal data touched or reproduced.
