verdict: accept-with-fixes
status: success

# harness-builder.REVIEW.REPORT — adversarial review of `depths-harness-fix-20260905`

Reviewer: pi worker (role: reviewer, `venice/qwen-3-8-2-4t-a95b`). Method: read spec → report →
every changed file; re-ran every verification myself (self-tests, py_compile, and full end-to-end
runs against my own `mock_serve` instance on 127.0.0.1:18977); inspected builder artifacts in
/tmp; code-inspected paths I could not safely execute (launcher relaunch). No repo file modified,
no commits, no ssh, no live-serve traffic. Temporary outputs written only under /tmp/review-*;
one transient `/home/jun/glm-bench-results/` dir created by the deprecation-path repro was
deleted (dir was absent before and after — verified).

## Claims table

| # | Report claim | Verdict | Receipt |
|---|---|---|---|
| 1 | 6 commits `c4a98f7 d06ccf5 796e4c7 4b510d8 629c3f2 ef051bb` on main, identity `Depths <depths@eva-core>`, trailer `Agent: depths`, pushed | **verified** | `git log 4bc9128..HEAD --format='%h %an <%ae>'` + `%(trailers:key=Agent)` → all 6 match; `git rev-parse HEAD origin/main` both `ef051bb`; `git log origin/main..HEAD` empty |
| 2 | Diffstat vs base: 7 files, +1866/−89, all under `scripts/` | **verified** | `git diff 4bc9128..HEAD --stat` exact match; `git status --short` → only `?? artifacts/` (untracked, as claimed) |
| 3 | bench_c4_steady v2: per-stream t_post/t_first/t_last/gaps/finish/usage+cached_tokens, `steady_agg_tok_s` + renamed `e2e_agg_tok_s`, TTFT + ITL p50/95/99, tokens/bundle, windowed spec/prefix/per-pos deltas, t0 quiescence + post-window gen reconciliation, invalid-pass flags recorded not crashed, `--passes/--cooldown/--out` O_EXCL, resolved env block | **verified** | Read code; self-test 23/23 PASS (re-run); my e2e: `--passes 1` no `--out` → single JSON to stdout with all fields (valid=True, steady 3712.1 / e2e 3699.2, ttft, itl_ms, cached=100, quiescence ok, metrics_delta incl. per-pos 0–6, config env block + prompt_sha256); `--passes 2` no `--out` → rc=2 argparse error; `--passes 2 --out` → `rev-20260905T081547Z-c4.json`, schema `c4_steady_v2`, 2 valid passes, summary block |
| 4 | Frozen conventions preserved exactly (CODE prompt, end-nonce, temp 0, thinking off, 1600/200) | **verified** | Programmatic compare vs `git show 4bc9128:scripts/bench_c4_steady.py`: `new CODE == old CODE: True`; sha256 `c69cfdc56e2be03e…` matches value embedded in builder's mixedguard artifact; request body identical (nonce at end, temp 0, `enable_thinking:false`, 1600 measured/200 warmup). Note: the builder spec text says "1600/400" but the base file was actually 1600/200 — builder preserved the real base convention (correct for comparability; 400 belongs to bench_decode_full C1) |
| 5 | bench_decode_full v2: real ttft_s, finish_reason, per-request cached_tokens toggle check replacing L110–127 global-counter block, per-phase windowed spec counters, `--runs` mean±sd, `--out` O_EXCL, deprecation warning + exit 2 on old path | **verified** | Old file confirmed (`ttft_s: None` hardcode, global-counter toggle, L133 dated path). Self-test 7/7 PASS. My e2e: ttft_s=0.001 real, finish lists printed, `spec_phases` = warmup + 8 C1 cells + c4 + thinking_toggle, toggle shows per-request cached ratio, `spec_counters_end` kept; no-`--out` run → loud stderr warning + wrote old path, second run → rc=2 `REFUSED` (then cleaned up) |
| 6 | run_cold_prefill: `--out` O_EXCL + timestamped default under /home/jun/glm-bench-results/, ladder/protocol untouched | **verified** | `git diff` is surgical (only OUT_JSON→argparse/O_EXCL/mkdir + docstring). My e2e full ladder vs mock: calibrated tokenize exact at 8k/16k/100k/300k (rel 0.000%), APC follow-up ran, cached_tokens=0 on all cold rungs, `Wrote /tmp/review-cold.json`, same-path rerun rc=2 |
| 7 | bench_mixed_guard: import-reuse of c4 functions, ONE front-salted ~16k cold prefill mid-window, injected TTFT/cached=0 proof, steady_agg retention, max per-stream stall, gen reconciliation incl. injected tokens, `--out` O_EXCL | **verified** | Code imports `bench_c4_steady`/`run_cold_prefill_18888`; salt is a unique random PREFIX. Builder artifact /tmp/mgout: retention 0.999, injected cached_tokens=0, gen_delta 8000 = 6400+1600. My e2e: retention 1.003, guard valid, cached=0, same reconciliation. Self-test 7/7 PASS |
| 8 | sweep_driver: no hardcoded configs, resolved env recorded, relaunch ONLY with `--relaunch`, health+warmup-completion polling (criterion recorded, never fixed sleep), quiescence, warm-until-stable (3 consecutive within 5%), scored passes, docker say-line + per-rank ssh telemetry, O_EXCL JSON, sweep.log phase lines | **verified (mechanics), with 2 real bugs below** | Self-test 17/17 PASS incl. no-hardcoded-configs source check. My e2e single-config run: env `{"REVIEW_K":"7"}` recorded, `criterion=regex` fired, quiescence ok, stable at warm pass 3, **3 scored passes (default)**, sweep.log one line per phase, `revA-…-sweep.json` O_EXCL, docker error recorded gracefully. Builder's /tmp/swout artifacts + /tmp/sweep-test.log corroborate two-config and two-distinct-file runs. Launcher shapes match `launcher.snapshot.sh` (container `glm53-exl3` L10, say-line `async=… k=… small_ok=…` L189, warmup log `/tmp/glm53-exl3-warmup.log` L298). **BUT** see bugs B1/B2 |
| 9 | `--self-test`: 23+7+7+17 = 54 checks, all PASS | **verified** | Re-ran all four: PASS counts exactly 23/7/7/17, all OK |
| 10 | py_compile all six, Python 3.14.7 | **verified** | All 6 OK; `python3 --version` = 3.14.7 |
| 11 | "sweep_driver two-config run … warmup **regex** criterion" | **false as attributed** | /tmp/sweep-test.log: the two-config legA/legB run (01:05–01:10) used `criterion=log_quiet_and_healthy` (120 s each). `criterion=regex` fired only in later single-config runs (builder artifacts + my run). Both criteria do work; the report mis-attributes which run showed regex |
| 12 | c4 "2-pass run with --out" e2e | **verified by reproduction; builder artifact missing** | /tmp/c4out is EMPTY (no surviving artifact). I reproduced the behavior end-to-end myself (row 3), so the capability claim stands |
| 13 | stdlib only, urllib-based, no installs | **verified** | All imports stdlib (argparse/json/os/re/sys/time/uuid/threading/urllib/hashlib/math/secrets/statistics/subprocess/pathlib/http.server); no third-party anywhere |
| 14 | mock runs on 127.0.0.1 only; no cluster/ssh/benchmark traffic | **verified (as far as observable)** | mock_serve binds 127.0.0.1 only; nothing listening on 18888 here; builder sweep tests used `--ranks local` (artifacts show `ranks=['local']`), so no ssh attempted. One borderline docker invocation — see constraints |
| 15 | Historical files untouched; artifacts/ untracked | **verified** | results/ and README.md absent from diff; `/home/jun/glm-bench-results/` did not exist on this machine before or after (historical evidence lives on forge); `git status` → only `?? artifacts/` |
| 16 | README-bench.md documents four rulers, named metrics, frozen conventions, bugs fixed, overwrite lesson, warmth protocol | **verified** | Read in full; all sections present and accurate (incl. honest labeling of the e2e formula as the client-wall window) |
| 17 | Report's residual-risk list (warmup regex permissive, per-pos absent positions, deprecated default path, old-key rename breaks uncommitted 09-04 wrapper, mock numbers meaningless, ssh/docker paths unproven) | **verified as honest** | Each risk checked against code/artifacts; all real and fairly stated. The report did NOT, however, disclose the C1 prompt change (V1) or bugs B1–B3 |

## Constraint violations

- **V1 (must fix) — undisclosed C1 prompt change.** Commit `d06ccf5` changed the bench_decode_full
  math prompt: `"pipe B alone in 4 hours"` → `"pipe B alone fills it in 4 hours"`
  (scripts/bench_decode_full.py:38, verified by AST diff vs `4bc9128`). Not mentioned in the
  commit message, REPORT, or README. The hard-constraint sentence pins the CODE prompt of
  bench_c4_steady.py (which IS byte-identical ✓), so this is not a literal violation, but the
  audit's own residual-risk rule — "if the builder changes … prompt text … all cross-day
  comparisons void" — applies to every ruler, and this silently breaks C1-math comparability
  with the 09-02/09-03 artifacts. Revert (preferred) or document + version explicitly.
- **Borderline — local `docker logs` invocation during verification** despite "no docker":
  builder artifacts record `docker_env_error: permission denied … docker.sock` (and one
  `requires 1 argument`). A harmless failed local CLI call; no container touched; intent of the
  constraint (cluster safety) not breached. Noted, no action.
- **Acceptable — transient writes outside scripts/ during verification**: the deprecation-path
  test inherently writes `/home/jun/glm-bench-results/bench_decode_2026-09-02.json`; on this
  machine that directory did not exist (historical evidence is on forge) and was cleaned up
  afterwards (I reproduced and re-verified absence). /tmp test outputs remain as receipts.
- Everything else clean: only `scripts/` touched in commits; each logical change committed
  separately with correct identity/trailer; pushed; no ssh attempted (`--ranks local`); no
  installs; no live-serve traffic; no personal data.

## Bugs found (file:line)

- **B1 (HIGH, must fix) — sweep_driver relaunch never exports the resolved env.**
  scripts/sweep_driver.py:300: `run_cmd(["bash", args.launcher], timeout=2400)` → `subprocess.run`
  with no `env=` parameter, and nothing anywhere updates `os.environ` (grep: only line 291 uses
  env, for the log line). Deliverable 5 says "per-config {export resolved env → relaunch …}".
  With `--relaunch`, every leg boots with the *caller's* environment; the per-config overrides —
  the entire point of the A/B/A — are silently not applied, while the artifact records an env
  block that was never in effect. This is precisely the silent-failure class the campaign exists
  to eliminate. Fix: `subprocess.run(..., env={**os.environ, **env})` (thread env through run_cmd).
  Not disclosed in the report; not caught by self-test or mock e2e (relaunch path never exercised).
- **B2 (MED-HIGH, must fix) — dmesg OOM false zero.** scripts/sweep_driver.py:246–248:
  `dmesg 2>/dev/null | grep -ci 'out of memory' || true` returns `"0"` with rc=0 when dmesg is
  unreadable. Confirmed on this host: `kernel.dmesg_restrict=1`, raw dmesg → "Operation not
  permitted", yet my own sweep artifact records `dmesg_oom_count: "0", dmesg_error: null` —
  indistinguishable from "no OOM events". Non-root ssh to forge/anvil/ember/flame will very
  likely hit the same restriction, silently satisfying the audit's "OOM counters zero" guard.
  Fix: check `dmesg` readability/rc separately and record an error (or `null`) when unreadable.
- **B3 (MED, must fix) — missing `--out` dir → crash AFTER the whole benchmark, data lost.**
  scripts/bench_c4_steady.py:506–508 and scripts/bench_mixed_guard.py:233–235 call `write_excl`
  without creating the parent directory. Reproduced both: valid pass(es) complete, then
  `FileNotFoundError` traceback, rc=1, results gone (receipts: /tmp/review-mg-stderr.txt first
  run; /tmp/review-c4-nodir-err.txt). The other three scripts mkdir correctly
  (bench_decode_full:248, run_cold_prefill:338, sweep_driver:399). On the live cluster this
  wastes minutes-per-pass measured runs on a typo'd or fresh `--out`. Self-tests missed it
  (they always use an existing TemporaryDirectory).
- **B4 (LOW) — duplicate invalid reason.** scripts/bench_mixed_guard.py:80–88: the
  `gen_delta=`-prefix filter does not remove `generation_tokens_total_unavailable`, which is then
  re-appended → duplicated reason string when /metrics is down.
- **B5 (LOW) — silent fallback in toggle check.** scripts/bench_decode_full.py:220: if r1 fails,
  the r2 history gets a fabricated assistant turn `"OK"`; only indirectly visible via `_pick`'s
  error entry.
- **B6 (LOW-MED) — exit codes don't signal failure.** sweep_driver returns 0 even for
  health_failed/warmup_timeout/not_quiescent/warm_unstable configs, and `_write`'s
  FileExistsError prints REFUSED but exits 0 — inconsistent with the other harnesses' rc=2.
- **B7 (LOW) — unbounded `docker logs`.** scripts/sweep_driver.py:224 fetches the full container
  log history (no `--tail`/`--since`); memory/time risk on a long-lived serve.
- Observations (no action required): mock_serve ignores request `max_tokens` (disclosed —
  "numbers are meaningless"); `e2e_agg_tok_s` keeps the historical client-wall formula per the
  builder spec's "rename existing number" while the audit proposed Σct/(max t_last − min t_post)
  — README labels the actual formula correctly; sweep artifacts embed the resolved config env but
  not c4's `config_block` (prompt_sha256/ruler version) — worth adding.

## What must change before accept

1. **V1**: revert the C1 math prompt in bench_decode_full.py to the exact historical text (or,
   if the change is deliberate, document + version it loudly in README-bench.md and the report).
2. **B1**: pass the resolved env to the launcher subprocess in sweep_driver (`env={**os.environ, **env}`).
3. **B2**: make the dmesg OOM count distinguish "unreadable" from "zero events".
4. **B3**: `Path(args.out).mkdir(parents=True, exist_ok=True)` in bench_c4_steady.py and
   bench_mixed_guard.py before `write_excl`.
All four are small (≈1–5 lines each); re-run the four `--self-test`s + py_compile after.
B4–B7 are optional polish.

## Summary for the orchestrator

The builder's report is substantially honest and the work is real: all six deliverables exist,
compile, and behave as claimed — I independently re-ran all 54 self-test checks and full
end-to-end runs of every harness against a fresh mock serve (including O_EXCL refusals, the
deprecation path, invalid-pass gating, the mixed-guard injection with cached_tokens=0 cold
proof, and a complete sweep-driver pipeline with the default 3 scored passes), and commit
hygiene (identity, trailer, granularity, push) is exact. Three findings block a clean accept:
an **undisclosed change to the C1 math prompt** in bench_decode_full (comparability drift of the
exact kind this campaign polices), a **sweep-driver relaunch that records the resolved config env
but never exports it to the launcher** (would silently void every --relaunch A/B/A leg), and a
**dmesg OOM counter that reads a false "0" whenever dmesg is unreadable** (confirmed on this
host; would silently pass the campaign's OOM guard on all four ranks). Plus a data-loss papercut:
bench_c4_steady and bench_mixed_guard crash after completing the benchmark if the --out directory
doesn't exist. None of these were disclosed in the report's risk list, and none are reachable by
the existing self-tests — fix the four small items (revert prompt, env= to subprocess, dmesg
error discrimination, mkdir parents) and this is accept.
