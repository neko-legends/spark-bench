# Upstream filing package — prepared, not yet posted

Status: **drafts ready; posting waits for the final champion numbers** (so each post can cite the
shipped config instead of a mid-campaign one). Prepared 2026-09-10 19:20 PDT.

Posting order I'd use (cheapest and most useful first):
1. SGLang parser PR (issue + PR) — we have a working patch.
2. Tony's issue #1 comment — pure data, no code.
3. SGLang DSpark corruption issue — evidence only, no fix.
4. Sero issue (and PR only if he asks).

Everything is filed under Jun's GitHub account. Nothing has been posted yet.

---

## 1. SGLang: `deepseekv41` tool parser drops parameters without `string=` — issue + PR

**Files:** `sglang-lane/patch_detector.py`, `sglang-lane/Dockerfile` (reproducible patch step).

### Issue body (draft)

> **`deepseekv41` tool-call parser silently drops parameters that omit `string="true"`**
>
> Serving DeepSeek-V4.1-Flash on `lmsysorg/sglang:dev-dsv41`, we found that the model at
> temperature 0 emits tool calls whose parameters do **not** carry the `string="true"` attribute:
>
> ```
> <function_call>lookup_fixture</function_call>
> <parameter name="key">alpha</parameter>
> ```
>
> `deepseekv32_detector.parameter_regex` requires the `string="..."` attribute, so the parameter
> is skipped and the model receives `arguments={}` — silently, with no error. The behaviour is
> deterministic at temperature 0 and reproducible across restarts.
>
> Evidence (raw `/generate`, 3/3 identical): [link]
> Tool round-trip fails: the model is told its call had no arguments.
>
> The same checkpoint works on vLLM's `deepseek_v41` parser, which accepts the attribute-less
> form, so this looks like a parser-grammar assumption rather than a model defect.
>
> Suggested fix: make the attribute optional and route the attribute-less form into the existing
> non-string branch (JSON attempt, then raw-string fallback). We have a patch that does exactly
> that and regression-tests all three states (`absent`, `string="false"`, `string="true"`);
> happy to open a PR if that's the preferred shape.

**PR plan (still to do before posting):**
- [ ] minimal repro against SGLang `main` (not just the `dev-dsv41` image)
- [ ] test added next to the existing detector tests
- [ ] confirm no behaviour change when the attribute *is* present
- [ ] final numbers from the campaign to cite in the PR description

---

## 2. tonyd2wild issue #1 comment (GB10 hidden fast/slow state)

**Repo:** `tonyd2wild/DeepSeek-V4.1-Flash-vLLM-DGX-Spark` issue **#1**. Comment, no code.

### Comment body (draft)

> Adding a fleet data point, and a second variable to consider.
>
> **Hardware:** 4× DGX Spark (GB10), 2× FE + 2× GX10, same RoCE topology (ours via a MikroTik
> CRS812), vLLM TP4, DSpark k=5, CUDA graphs `FULL_AND_PIECEWISE`, DeepSeek-V4.1-Flash.
>
> **Setup difference:** we run `nvidia-smi -lgc 0,2200` as a systemd unit on every node
> (`spark-gpu-clock-lock`), i.e. a *hard* SM clock lock, not just "no throttle reason".
>
> **Result:** using your `gpuflip.py`/`flipsum.py` unchanged, all four nodes read **fast** and
> stayed fast:
>
> | node | gemv_duty p50 | gemv_cont p50 | flips |
> |---|---:|---:|---:|
> | forge | 215.7 GB/s | 217.6 GB/s | none |
> | anvil | 214.7 | 217.6 | none |
> | ember | 214.3 | 218.0 | none |
> | flame | 214.9 | 217.9 | none |
>
> (60 s windows, all-fast 60 s / slow 0 s per `flipsum`.) We also re-ran the probe after a full
> node reboot: still fast.
>
> **Caveat:** one node was rebooted before the probe, and all four have the clock lock active
> from boot — so we can't separate "this fleet never latches" from "the hard clock lock prevents
> it". Worth testing whether `-lgc` at boot is enough to hold the fast state on your two latched
> boxes; if it is, that's a cheaper fix than the unplug dance.
>
> **Unrelated but possibly useful to you:** switching DSpark's `draft_sample_method` from
> `probabilistic` to `greedy` (temp 0 workloads) gave us **+30% C1 coding, +36% math, +31%
> prose** on this hardware with acceptance mean 4.12 → 4.36. If your bench is temp 0, that's a
> free win.

**Still to do:** copy in the final `gpuflip`/`flipsum` outputs from `gpuflip/` and the final
C1 numbers from `phase4/RESULTS.md`.

---

## 3. SGLang: DSpark corrupts output on GB10 (SM 12.1) — issue only

**Evidence:** `sglang-lane/dspark-corruption-repro/` (6 configs), `STATUS-sglang-phases1-2.md`.

### Issue body (draft)

> **DSpark speculative decoding deterministically corrupts output on GB10 (SM 12.1)**
>
> **Stack:** `lmsysorg/sglang:dev-dsv41` (arm64), 4× DGX Spark (GB10, cc 12.1, 128 GB unified),
> multi-node `--nnodes 4 --tp 4 --ep-size 4` over ConnectX-7 RoCE, `--attention-backend dsv4`,
> `--moe-runner-backend flashinfer_mxfp4`, DeepSeek-V4.1-Flash (native FP4 experts / FP8 dense,
> Engram tables read from NVMe per rank — needed to fit; that adapter is 0xSero's row-store
> design and it runs clean with DSpark on 4× RTX PRO 6000, single node).
>
> **Symptom:** with `--speculative-algorithm DSPARK`, the assistant turn following a
> `<tool_result>` emits a runaway of the parameter/close tags rather than prose. Deterministic:
> 3/3 byte-identical at temperature 0 via raw `/generate`. Identical prompt with speculation off
> answers correctly, 3/3.
>
> **Configs tried — all corrupt, bytes identical or same family:**
> `--disable-cuda-graph-padding`; `--speculative-dspark-align-verify-tokens-to-graph-tier`;
> `--speculative-dspark-block-size 4` (5 too); SWA bounded-replay off. Eager+spec was
> inconclusive (probe timed out; eager is ~5 tok/s on this hardware).
>
> **Speculation off:** arithmetic, JSON-schema, tool round-trip, 7/7 correctness gates, NIAH
> 32k+100k 12/12, vision, and a 5-minute 4-concurrent soak all pass.
>
> **Speed when speculation is on** (before the corruption check): 39–46 tok/s single stream at
> accept length 3.0–4.7, so the feature is worth ~3× on this hardware if it can be made correct.
>
> **Related:** PR #38879 ("Optimize DSpark verify and MoE kernels on Blackwell") merged *after*
> our image was built; we intend to retest on a post-#38879 build. Also possibly related in kind:
> closed PR #33872 (compress-ring under-write under speculative verify on DSV4).
>
> Repro commands and raw outputs: [link]. Happy to test patches.

**Still to do:** retest on a post-#38879 build before filing; add the final repro command block;
final numbers.

---

## 4. 0xSero: parallel Engram row reader — issue first, PR only if wanted

**Repo:** `0xSero/deepseek-v4.1-flash-4x-rtx-pro-6000`. Our patched reader:
`sglang-lane/` (draft `row_store.cpp`, `bench_row_store.py`) — note: **never built or measured**,
so the issue leads with measurements, not a claim.

### Issue body (draft)

> **Parallel Engram row reads — measurements + offer**
>
> Your README lists an io_uring/B12x reader as the next priority and notes the container hit
> `io_uring_setup EPERM` and a missing `liburing`. Two data points from a different box
> (4× GB10, Samsung MZALC4T0HBL1 NVMe, the real V4.1 Engram shards) that may be useful:
>
> | access pattern | per-row cost |
> |---|---:|
> | serial `pread` (one at a time) | ~300 µs |
> | parallel, QD 64–128, plain threads | ~17 µs |
> | page-cached (hot rows) | ~0.4 µs |
>
> At decode sizes (~64 rows/token, 2 layers) the difference between serial and parallel is
> ~19 ms vs ~1 ms per step — on a ~65 ms step for us. Cold prefill is worse: 6–10 tok/s serial
> vs 200+ tok/s warm on the same box, i.e. the reader, not the disk, was setting the floor.
>
> We drafted a reader that batches all rows of both layers into one submission (your
> `row_store_lookup` shape kept, cache/eviction semantics unchanged) but never built or measured
> it, and we're not proposing it blind. If useful: happy to send it as a PR so you can A/B it
> against your B12x direction, or as a reference patch in an issue. Either way, the serial-vs-
> parallel gap above is the reason your "engram lookup idles the GPU every step" line matches
> what we measured.

**Still to do:** decide issue vs issue+PR after his response; do not claim untested numbers as
ours (the table is measured; the draft reader is not).
