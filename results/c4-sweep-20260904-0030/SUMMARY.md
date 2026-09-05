# C4 sweep c4-sweep-20260904-0030

Ruler: bench_c4_steady.py (4 concurrent 1600-token code streams, thinking off) on forge. One toggle per boot on top of config C. Reference points: 08-28 serve 253 agg; 09-03 config C 128.9 agg.

| config | env | agg tok/s (client wall) | server gen tok/s | per-stream | boot s | OOM/5min before→after (forge anvil ember flame) |
|---|---|---|---|---|---|---|
| baseline-C | `(config C)` | **106.4** | 106.4 | 30.0 / 31.4 / 24.7 / 33.5 | 855 | 0 0 0 67 → 0 0 0 0 |
| async-off | `ASYNC_SCHEDULING=0` | **115.0** | 115.0 | 35.0 / 29.0 / 31.7 / 31.7 | 716 | 186 187 134 207 → 0 0 0 0 |
| mnbt-1024 | `MAX_NUM_BATCHED_TOKENS=1024` | **119.6** | 119.6 | 30.7 / 30.4 / 31.8 / 30.5 | 1255 | 0 0 0 0 → 0 0 0 0 |
| no-drafter-group | `SKIP_PATCHES=patch_glm5_drafter_group.py` | **134.4** | 134.4 | 35.3 / 35.1 / 34.1 / 34.0 | 919 | 0 0 0 0 → 0 0 0 0 |
| no-spinwait | `SKIP_PATCHES=patch_spinwait.py` | **131.8** | 131.8 | 33.4 / 35.8 / 33.9 / 33.4 | 688 | 113 89 31 0 → 0 0 0 0 |
| no-decode-floor | `SKIP_PATCHES=patch_scheduler_decode_floor.py` | **135.8** | 135.8 | 36.8 / 35.1 / 34.8 / 34.3 | 1195 | 58 0 96 0 → 0 0 0 0 |

## Reading this honestly (reviewed 2026-09-04 before publishing)

- Single bench run per config, first run after each boot = cold-cache regime.
  That is why baseline-C reproduces at 106.4, below the 128.9 the verified
  config-C run saw with a warm cache. Compare deltas against baseline-C, not
  against 253 or 128.9.
- Removing ANY of the three 09-02 patches helps ~+25% (131.8-135.8 vs 106.4).
  Removing async scheduling and shrinking MNBT help too. No single toggle
  approaches the 08-28 serve's 253. Conclusion: the 4-stream regression is
  shared across the 09-02 patch set (and possibly interacts with async
  scheduling / MNBT), not attributable to one culprit.
- Single-stream C1 stayed at parity throughout — this regression is specific
  to concurrent decode.
- Next lever, if we want it: a 2-patch-removal combination run (e.g.
  drafter-group + decode-floor) to test for interaction effects, plus a
  warm-cache re-baseline of config C to separate cache-warmth from the
  regression.
