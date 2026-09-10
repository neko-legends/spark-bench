verdict: accept-with-fixes

# Adversarial review — `depths-qwen38-recipe-20260905` (image & launcher recipe)

Reviewer: `venice/qwen-3-8-2-4t-a95b` (independent of builder `venice/z-ai-glm-5-3`).
Method: every concrete claim in `image-recipe.REPORT.md` re-verified with real commands
(fresh repo clones at the pinned commits, byte-level diffs, Docker Hub registry API,
GitHub API, HF HTTP-Range safetensors-header parse, read-only ssh to forge, full
builder-transcript audit, empirical dry-runs of both script layers). Nothing was
fixed, committed, or modified; this file is the only write.

## Claims table

| # | Report claim | Verdict | Receipt |
|---|---|---|---|
| 1 | blazux repo HEAD `b76890d5a033dd00166c792393d39cf908f56034` | **verified** | fresh clone; `git rev-parse HEAD` matches exactly |
| 2 | getrefined HEAD `f736930b636d2dbb4c7f4746311cbac66d8d2a6e` | **verified** | fresh clone; rev-parse matches |
| 3 | tsw2k HEAD `497a58e38b63f2223fb376901c3e4c5ede492efe` | **verified** | fresh clone; rev-parse matches |
| 4 | Vendored patches byte-identical to tsw2k @ 497a58e (and = blazux @ b76890d) | **verified** | `diff`/`cmp` on all 9 src files + NOTICE: identical to `tsw2k/src/`, `tsw2k/NOTICE`, and `blazux/src/` |
| 5 | getrefined `ple-force-fp8.patch` is the 3-line resolver, placed ABOVE the `isinstance(quant_config, Fp8Config)` gate | **verified** | `diff -q` identical; patch hunk inserts `PLE_FORCE_FP8` early-return directly above the gate |
| 6 | kernel-det 6 files = jschmied @ `20f64c4c`, byte-identical to blazux's `ADD --checksum` pins | **verified** | jschmied clone; `git show 20f64c4c` copies `cmp`-identical; all 6 sha256 in `patches/SHA256SUMS` equal blazux Dockerfile pins (lines 110–115) |
| 7 | `SHA256SUMS` covers 19 files | **verified** | `sha256sum -c` on 19 entries: all OK |
| 8 | `vllm/vllm-openai:qwen38-flash-next` exists; tag digest today = `sha256:fc120ece…bf8`; arm64 `3b0e188f…`, amd64 `0aea3024…`; pushed 2026-08-26; 9.7 GB | **verified** | registry API with auth token: `docker-content-digest: sha256:fc120ece0a388cc0aa1caad4a9f1cd92113484ab7ec2fd0efadd62585be05bf8`; manifest list arch digests match; Hub tag API `tag_last_pushed 2026-08-26T13:06:10Z`, `full_size 9702868146` |
| 9 | That digest is what tsw2k AND blazux pin | **verified** | `FROM …@sha256:fc120ece…` at tsw2k `Dockerfile:21` and blazux `Dockerfile:21` |
| 10 | Image label `ai.vllm.build.commit=unknown` (local pipeline build) | **verified** | pulled arm64 config blob `sha256:d464f3b4…`: `"ai.vllm.build.commit": "unknown"`, `"ai.vllm.build.pipeline": "local"` |
| 11 | Model-card commit `d4d703caf` NOT in image; = vllm#54882 "[Bugfix][Model] Fix FP8 PLE loading in mixed ModelOpt checkpoints", 2026-09-03, extends `_get_ple_embedding_quant_method` for ModelOpt mixed precision | **verified** | GitHub API: exact title, committer date 2026-09-03T17:09:39Z, touches `vllm/models/qwen4_exp/nvidia/ple_layer.py` (post-rename tree → cannot be in a 2026-08-26 pre-rename image); diff adds `ModelOptMixedPrecisionConfig` branch with `_resolve_quant_algo(prefix) == "FP8"` — exactly as described |
| 12 | Model card: arch `Qwen4ExpForConditionalGeneration` / `qwen4_exp`, 48 layers, 512 experts (10 active, moe_int 640), 24/2 heads, native 262144, vision_config, 125B/6B+51B PLE+4B MTP, 1M extensible, ~2.7× smaller, TP8 + `--quantization modelopt` + `--reasoning-parser qwen3` + `--trust-remote-code` sample, gen temp 1.0/top_p 0.95/top_k 20 | **verified** | fetched `config.json`, `generation_config.json`, `README.md` from HF resolve/main; all fields match (ModelOpt producer version is `0.46.0.dev281+g73d778422` — report's "v0.46.0" is fine) |
| 13 | PLE layout: 128 F8_E4M3 shards `[2500012,160]` + one BF16 `[1]` `ngram_embedding.weight_scale` in `model-fp8-mtp-ple.safetensors`; 53.72 GB; 25 files / 132.7 GB total; index maps all 128 shards to that file | **verified** | HTTP Range fetch of the safetensors header (416,360 B) parsed: 128 shards F8_E4M3 (2500012,160), BF16 [1] scale, 3072 MTP-expert tensors; `x-linked-size 53717551730`; index.json: 11 safetensors files, `total_size 132639846394`; shard keys all map to the fp8-mtp-ple file; matches `vllm_ple_mmap._find_shards()`/`_read_scale` (BF16 branch present) |
| 14 | Forge read-only state: download running (then), NCCL 2.30.7 @ `~/nccl-2.30.7` 253 MB, rail B `192.168.10.1/24` MTU 9000, HCA `roceP2p1s0f1`, ~250 GIDs, 2.3 TB free | **verified (now: download DONE)** | read-only ssh: `libnccl.so.2.30.7` 253,766,464 B; `enP2p1s0f1np1 UP 192.168.10.1/24`, MTU 9000; HCA present; 255 GID indices; 2.2T avail; download log now prints `DONE` (25/25 files), 11 safetensors, `du` 124G — consistent with the report's earlier snapshot |
| 11b | "GLM live (container glm53-exl3, up 54 min)"; "glm-cluster-watch.service active" | **verified-at-check-time, stale at write time** | builder's forge ssh ran 10:05:44 PDT (transcript timestamp); an external actor stopped both watchdogs at 10:12:39 and GLM exited(0) ~10:13 — see constraint audit; report (written 10:20) still said "live/active". Not builder-caused, but the report reads as current-tense |
| 15 | tsw2k facts: day-0 image = vLLM 0.1.dev20073 torch 2.13 cu130; layout `vllm/models/qwen3_8_flash_next/`; rename PR #53896 branch `peakcrosser7/vllm` `release/qwen38next`; EP mandatory at TP4 (NVFP4 padding); nofile 1M; never hardcode GID_INDEX; MTP k=2 acceptance 0.856; MNBT 8192 (2048 deep); `--mamba-block-size 1024` moves the #54629 wall; lane B resident boots at 0.78; SS 31.0, agg 97.0@8 / 157.0@16; KV pool 5,211,726; `message.reasoning` client note; gate suite G1–G5 with `--base/--model/--niah` | **verified** | tsw2k `Dockerfile:23`, `README.md:25-41,65-69,219`, `docs/TP4-DESIGN-NOTES.md:3-18`, `docs/OPEN-PROBLEMS.md:66-90,114-115`, `launch-qwen38-tp4.sh:41-49,112,143`, `evals/gate_suite.py:5-13,134-140` |
| 16 | getrefined facts: TP2+EP, MTP3, FULL_DECODE_ONLY (`{"mode":0,…}`), resident PLE, GMU 0.80, exact-HCA-pin gotcha (`=rocepXsYfZ`) | **verified (one overstatement)** | `launch-vllm-fn.sh:22,55-67`, `README.md:111-115`. Overstatement: getrefined does NOT set `cudagraph_capture_sizes` — sizes `[1,2,4,8]` come only from Jun's spec and are not validated in any published recipe (report says "getrefined … + capture sizes" / "exactly the spec's sizes, getrefined-proven") |
| 17 | R1 premise: checkpoint adds `mtp.layers.0.mlp.experts` as 128×128 block-scaled FP8 config group under MIXED_PRECISION | **verified (count nit)** | config.json `config_groups`: group_0 NVFP4 (4-bit, gs 16) main experts; group_1 FP8 8-bit gs 128 `mtp.layers.0.mlp.experts`; group_2 FP8 PLE — that's **three** groups, report says "two groups" |
| 18 | Deliverables exist; all vendored .py pass `py_compile`; both script layers pass `bash -n`; inner arg assembly dry-runs for all 3 cudagraph lanes × head/headless × MTP on/off × moe on/off | **verified** | all 12 .py compile; `bash -n` clean on launcher + extracted inner heredoc; stub-`vllm` dry-run reproduced lanes piecewise/full/eager — args exactly as documented, JSON flags (`--speculative-config`, `--compilation-config`) intact in argv |
| 19 | SPLIT list is blazux's verbatim | **verified** | byte-identical string at blazux `scripts/serve.sh:81` and tsw2k `launch-qwen38-tp4.sh:49` |
| 20 | Port discipline: GLM owns 18888 / master 25000; this lane 8000 / 25100 | **verified** | `astra-perf-20260905/launcher.snapshot.sh:17-18` vs launcher `PORT=8000`, `MASTER_PORT=25100` |
| 21 | NCCL donor `local/glm53-exl3:e2` exists on forge | **verified (path unverified)** | forge `docker images` lists `local/glm53-exl3:e2`; the in-image `nvidia/nccl/lib/libnccl.so.2` path could not be confirmed without running docker (out of scope) — launcher fails loudly if staging fails, so contained |
| 22 | Runbook `gate_suite.py --base … --model … --niah 4096,32768,131072` | **verified** | argparse accepts exactly these flags; `--niah` is a free size list |
| 23 | "Nothing on the sparks was modified; only read-only ssh to forge; no docker anywhere; watchdogs documented not modified; files uncommitted" | **verified** | full builder session transcript audited (`~/.pi/agent/sessions/--home-jun-git-spark-bench--/2026-09-05T16-58-46-167Z_….jsonl`, 62 tool calls): exactly 2 ssh invocations, both `forge`, both purely read-only (ls/du/ps/df/tail/systemctl list/docker images/docker ps/ip); zero local docker commands (only Docker-Hub HTTPS API); systemctl only `list-*`/`is-active`/`cat`; no git commit/add/push; no ssh to anvil/ember/flame or 192.168.10.2-4 except inside written artifact text; all writes under the artifacts dir |
| 24 | PREFLIGHT-CHECKLIST maps every spec line | **verified** | walked Jun's spec paragraph line-by-line against the checklist; every line has a row; conflicts (FULL_DECODE_ONLY vs mmap; marlin; CROSS_NIC; model-card sample flags) disclosed, none silently dropped |

## Hard-constraint audit (spec task 5 + review method)

| Constraint | Result |
|---|---|
| No image builds / no docker run anywhere | **pass** — transcript: zero docker CLI calls; only registry HTTPS API |
| No ssh to sparks beyond read-only forge checks | **pass** — 2 ssh calls, both forge, both read-only (full text audited) |
| No serve started, GLM not taken down, download not restarted | **pass** — no such commands in transcript; forge download completed on its own (log `DONE`) |
| Watchdogs documented, not modified | **pass** — only `systemctl list-*`/`is-active`/`cat` in transcript. Note: both watchdog units were stopped at 10:12:39 PDT by an actor outside this worker (the same second also stopped the unrelated `eva-kv-catchup.service`; journalctl shows systemd user-manager stops, builder transcript has no stop command). This makes the report's "glm-cluster-watch active / GLM live" stale, not false-at-check |
| Nothing modified outside artifacts dir; no commits | **pass** — `git log ef051bbe..HEAD` empty in both repos; spark-bench only has untracked `artifacts/`; builder writes all under `artifacts/qwen38-nvfp4-20260905/` (plus inert /tmp scratch: `/tmp/qwen38-card/` HF downloads — ephemeral, no durable change; eva-core's dirty `data/` files predate the run: mtimes 06:40 and Sep 4) |
| No personal data / secrets in deliverables | **pass** — grep for keys/tokens/passwords: clean |

## Bugs found (none caught by `bash -n` or the builder's inner-script dry-run)

1. **CRITICAL — launcher always aborts at rank 3 even on a healthy boot.**
   `launch-qwen38-tp4.sh:328`: `docker ps --format '{{.Names}} {{.Status}}' | grep -x '$CONTAINER'`.
   The format prints `qwen38-nvfp4 Up 3 seconds`; `grep -x` requires the WHOLE line to equal
   `qwen38-nvfp4` → never matches → the `||` branch runs `docker logs … ; exit 1` → launcher
   reports "RANK 3 EXITED" and dies before launching ranks 2/1/0. Demonstrated empirically
   (`printf 'qwen38-nvfp4 Up 3 seconds\n' | grep -x qwen38-nvfp4` → no match). tsw2k's
   equivalent check uses substring `grep "$NAME"` (their launcher:158). Fix: `grep -q "^$CONTAINER "`
   or `--format '{{.Names}}'` with `grep -x`.
2. **CRITICAL — SPLIT_OPS JSON is mangled by the docker-env round-trip (default lane).**
   `launch-qwen38-tp4.sh:297` writes `-e SPLIT_OPS="$SPLIT"` into the generated
   `/tmp/qwen38-docker-r$rank.sh`; when bash re-parses that file, the inner JSON quotes are
   consumed as shell quoting. Demonstrated empirically: docker receives
   `SPLIT_OPS=[vllm::unified_attention_with_output,…]` — no double quotes — so the inner
   script passes `-cc.splitting_ops=[vllm::…]`, which is not valid JSON. The default
   piecewise+mmap lane will fail (or misparse) at engine start on every rank. tsw2k avoids
   this by putting `-cc.splitting_ops="$SPLIT"` directly in the `vllm serve` argv. Fix:
   single-quote the value in the generated file (e.g. emit `-e SPLIT_OPS='$SPLIT'` with a
   quoted heredoc for that line) or pass the JSON through a mounted file / argv.
3. **MEDIUM — documented OOM fallback silently doesn't work on the resident lane.**
   `launch-qwen38-tp4.sh:99`: `PLE_MODE=resident` overwrites `GPU_MEM_UTIL` with
   `${GPU_MEM_UTIL_OVERRIDE:-0.78}` — so the documented `GPU_MEM_UTIL=0.75 ./launch…` fallback
   is ignored on the spec lane, and the env var that actually controls it
   (`GPU_MEM_UTIL_OVERRIDE`) is documented nowhere.
4. **MINOR — dead/misleading Dockerfile CMD.** `Dockerfile.qwen38-gb10:141`: the base image's
   ENTRYPOINT is `["vllm","serve"]` (verified from the arm64 config blob), so
   `CMD ["python3","-c",…]` becomes *arguments to `vllm serve`*; a bare `docker run` of the
   built image errors instead of printing the friendly message. All documented invocations
   override `--entrypoint`, so cosmetic — but it will confuse an operator.
5. **MINOR — preflight can't self-heal a stale own container.** The co-residency guard
   (`launch-qwen38-tp4.sh:120`) counts ALL GPU compute apps and fails *before* preflight's own
   `docker rm -f $CONTAINER` (line ~125) runs; a leftover `qwen38-nvfp4` from a crashed boot
   trips it with the misleading "(GLM up?)" hint. Runbook step 6 tells the operator to rm -f
   first, so it fails safe — just not self-recovering.
6. **MINOR — `NCCL_IB_HCA=roceP2p1s0f1` (line 74) is prefix-match, not "EXACT single-device
   pin" as commented.** getrefined's own gotcha (README:115) recommends `'=rocepXsYfZ'`.
   Functionally OK here (prefix is unique among forge's 4 HCAs and matches the proven GLM
   launcher), but the comment overstates NCCL semantics; adding `=` costs nothing.
7. **MINOR — report/checklist wording inaccuracies:** (a) capture sizes `[1,2,4,8]` attributed
   as "getrefined-validated shape" — getrefined validates FULL_DECODE_ONLY only, the sizes are
   spec-only/unproven; (b) R1 says quant config has "two groups" — there are three
   `config_groups`; (c) PREFLIGHT line 16 says flusher-unconditional.sh is "documented in the
   report" — REPORT.md never mentions it (dangling cross-reference); (d) typo "getrefiven";
   (e) "GLM live / watchdog active" written in present tense though both changed at 10:12–10:13
   by a third party before the report was written.
8. **COSMETIC — preflight disk check** `df --output=avail -k $MODEL_HOST` fails when the dir
   doesn't exist yet, reporting "<20GB free near model dir" instead of "weights missing"
   (fails safe either way).

## What must change before accept-as-executable

- Fix bug 1 (`grep -x` liveness check) — without it, no boot can ever proceed past rank 3.
- Fix bug 2 (SPLIT_OPS quote stripping) — without it, the default lane's `-cc.splitting_ops`
  receives invalid JSON on every rank.
- Re-run the dry-run harness *through the generated docker-run script layer* (not just the
  inner heredoc) — both critical bugs live in that untested layer.
- Recommended (non-blocking): fix bug 3 (GPU_MEM_UTIL vs resident lane), the CMD line, the
  `=`-prefix HCA pin, and the wording nits in 7(a)–7(e).

## Summary for the orchestrator

The research half of this deliverable is outstanding and survived a full independent
re-verification: all three patch repos plus jschmied's kernel repo were re-cloned at the
claimed commits and every vendored file is byte-identical to its source (kernel files also
match blazux's `ADD --checksum` pins); the Docker Hub tag digest, both arch manifests, push
date and size, the image's `build.commit=unknown` label, the #54882 identity/date/content of
the model-card commit, the HF config/generation/quant files, and the 128-shard F8_E4M3 PLE
layout (parsed live from the safetensors header over HTTP Range) all reproduce exactly; the
forge-side state claims reproduce (download has since completed cleanly); and a full audit of
the builder's session transcript proves every hard constraint was honored (two read-only ssh
calls to forge, zero docker, zero watchdog modification, zero commits, writes only inside the
artifacts dir — the watchdog stops and GLM teardown at 10:12–10:13 were an external actor,
which merely made two report sentences stale). However, the launcher — the thing Depths will
actually execute — contains two demonstrated, boot-blocking bugs that its verification
methodology could not catch: the post-start liveness `grep -x` can never match (every launch
aborts at rank 3 even when healthy), and the SPLIT_OPS JSON loses its quotes through the
generated docker-run script (the default piecewise lane gets an invalid `-cc.splitting_ops`),
plus a medium env-override trap on the resident lane. All are one-to-few-line fixes with
proven patterns sitting in tsw2k's launcher. Verdict: **accept-with-fixes** — accept the
image recipe, patch stack, provenance and checklist as final; the launcher must be patched
and its docker-script layer re-dry-run before the runbook is executed.
