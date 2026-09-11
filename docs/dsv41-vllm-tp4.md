# DeepSeek V4.1 Flash — 4× DGX Spark

> **Draft section for `README.md`.** This is the staging file for the
> "DeepSeek V4.1 Flash — 4× DGX Spark" section, following the same *honest-map*
> protocol as the [DeepSeek V4 Flash](#deepseek-v4-flash) section above it:
> every number carries prompt depth, task type, and thinking state. It is **not**
> yet folded into `README.md` — that happens at final publish, once Stage C
> gives us the frozen champion table. Numbers marked `TODO(final)` change.

<a id="deepseek-v4-1-flash"></a>

Uncensored DeepSeek V4.1 Flash 0909 (non-abliterated, full checkpoint), vLLM +
DSpark speculative decoding, TP=4 on the same switched RoCE fabric as the V4
Flash recipe. The second-generation port: newer model, newer engine, same four
GB10s. SGLang was the first lane; it was correct-but-slow with speculation off
and corrupt with speculation on, so the ship config is vLLM.

**In plain English:** it writes answers at **~71 tokens/second** for one person
on a coding task (**~73** on math, **~29** on prose), serves **six people at
once** at **~132 tokens/second combined**, and reads long prompts at
**~1.0–1.5k tokens/second**. It ships with a **420k-token context window**,
tool calling and vision **on**, with a speculative decoder keeping about
**4.4 tokens per step**. The headline is the *best case* — short prompt, code
output. At real conversation depth the same hardware gives **~44–47 tok/s**;
see [the honest map](#the-honest-map-what-speed-you-actually-get-1).

The single biggest number, though, is not a speed: **the exact tool round-trip
that corrupted deterministically under SGLang + DSpark is byte-clean under
vLLM + DSpark.** That is why this lane ships.

![Four-node DGX Spark dashboard: DeepSeek-V4.1-Flash TP4 live on forge:8000, 420k context, DSpark spec decode](docs/images/dsv41-vllm-tp4-dashboard-2026-09-10.webp)

*The live TP4 world, 2026-09-10: forge head + anvil/ember/flame, served id
`deepseek-v4.1-flash`, 430080-token window. Dashboards are modified
[MiaAI-Lab sparkDash](https://github.com/MiaAI-Lab/sparkDash).*

## Current champion numbers (2026-09-10, 420k boot)

All rows: temperature 0, thinking off, after warmup, on the accepted champion
config (`DRAFT_METHOD=greedy`, DSpark k=5, 420k = `MAXLEN=430080`). Source:
[`artifacts/dsv41-vllm-20260910/CHAMPION.env`](artifacts/dsv41-vllm-20260910/CHAMPION.env)
and [`STATUS.md`](artifacts/dsv41-vllm-20260910/STATUS.md). The **Stage C
re-table** (the frozen publish table, A/B/A on the final champion) is still
running — values here are the campaign snapshot, not the freeze.

| metric | value | conditions |
|---|---:|---|
| C1 per-stream decode — **coding** | **70.8 tok/s** | 420k boot, short prompt, code task, greedy draft |
| C1 per-stream decode — **math** | **72.9 tok/s** | same; +36% from greedy draft |
| C1 per-stream decode — **prose** | 29.1 tok/s | same; prose is the weak category (accept ≈2 tok/step) |
| C6 aggregate | **132 tok/s** (27.1/stream) | six concurrent streams; parity with tonyd2wild boot-10 (131.86) |
| C1 record protocol (`bench-decode`, 2048 tok) | 72.4 tok/s median (min 67.4) | greedy, no 48-tok/s mode observed |
| cold prefill | 1,494 / 1,521 / 1,520 / 1,447 / 1,186 tok/s | 2k / 8k / 32k / 64k / 100k unique-prefix prompts |
| DSpark acceptance | 4.36 mean tok/step · 67% rate | greedy draft, n=71 windows (median 5.02) |
| KV pool | 1,530,285 tokens @ 430080 window (3.56×) | GMU 0.80, `nvfp4_ds_mla`, block 128 |
| sequence cap (advertised) | **4** | C4 = 56% of C1 per-stream; C6 43%; C8 27% |
| context | 430,080 tokens | reserved catch-up window |
| served id | `deepseek-v4.1-flash` | `http://forge:8000/v1` |

Anchor for context: our V4 Flash on the same fabric did 136 tok/s C1 best-case,
66–93 at real chat depth, 182 at C4. **V4.1 Flash is slower than V4 Flash** on
this hardware the same day — newer model, heavier MoE routing, and the greedy
draft only partly closed the gap. Quote the model, not just the cluster.

## The honest map: what speed you actually get

| workload | decode tok/s | status |
|---|---:|---|
| Best case: short prompt, coding, long run | **70.8** | measured |
| Short prompt, math | 72.9 | measured |
| Short prompt, prose | 29.1 | measured |
| 5k prompt | 46.7 | measured (`bench-depth`, 420k baseline) |
| 10k prompt | 43.5 | measured (`bench-depth`, 420k baseline) |
| Deep session (~50k prompt) | `TODO(final)` | bench-depth at depth not yet run on the frozen champion |
| 5–10k prompt, regular chat / prose | `TODO(final)` | category × depth matrix pending |

`TODO(final)`: the whole 5k/10k/50k table is being re-measured on the final
champion; the 5k/10k rows above are the 420k probabilistic-draft baseline and
may move ±5–10% with the greedy draft. When the final numbers land, replace
this table with the same depth × category × thinking grid used in the V4 Flash
honest map. Do **not** publish a single C1 number as "the speed" — a short-prompt
code cell and a 50k agent turn are different measurements.

## How to run DeepSeek V4.1 Flash (recipe)

**You need:**

- 4× DGX Spark (GB10), one 200G cable each into the same RoCE switch, wired per
  [`docs/FABRIC.md`](docs/FABRIC.md). This port runs **rail B**: interface
  `enP2p1s0f1np1`, HCA `roceP2p1s0f1`, subnet `192.168.10.0/24`, MTU 9000.
- The **model on all four nodes** at `/home/jun/models/deepseek-v4.1-flash`,
  mounted read-only as `/models/DeepSeek-V4.1-Flash`:
  [`deepseek-ai/DeepSeek-V4.1-Flash`](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash)
  @ `fb2764a5` (510 GB). **No NFS, no per-worker sparse copy** — every rank
  reads weights *and* engram rows from local NVMe.
- The engine image on **all four nodes**: `local/vllm-dsv41:overlay5`. It is a
  node-local build (IDs differ per node — verified by the runtime no-JIT gate,
  not by image digest). The chain, all from the
  [tonyd2wild recipe](https://github.com/tonyd2wild):
  ```text
  vllm/vllm-openai:nightly-8a728663c1c3...        (base)
    + vLLM dsv41-feat @ e47aa780 (python tree)
    + _C_stable_libtorch rebuilt sm_121a            → overlay1
    + FlashInfer 0.7.0rc1 @ 07869c61                → overlay3
    + mxfp8_gemm_cutlass_sm120 (prebuilt, MAX_JOBS=4) → overlay4
    + sparse_mla rebuilt under runtime env           → overlay5 = local/vllm-dsv41:overlay5
  ```
  Full build record in
  [`artifacts/dsv41-vllm-20260910/Dockerfile`](artifacts/dsv41-vllm-20260910/Dockerfile)
  and `STATUS.md` §S2.
- The **8 bind-mounted vLLM patch files** in `~/patches/dsv41-boot10/` on every
  node (7 patches + `mounts.txt`), md5-identical to tonyd2wild boot-10:

  | file | md5 | role |
  |---|---|---|
  | `engram.py` | `c0329107` | engram-on-disk + rank offsets |
  | `weight_utils.py` | `7e1027f1` | local shard loading |
  | `model_state.py` | `0a14bee6` | DSV4.1 state / MLA |
  | `attention.py` | `da9ef196` | SM12x attention |
  | `flashinfer_sparse.py` | `af0f8447` | sparse MLA on FlashInfer |
  | `sparse_swa.py` | `cc419353` | sliding-window attention |
  | `sparse_attn_indexer.py` | `a9b73756` | sparse indexer |
  | `mounts.txt` | `79a774bc` | bind map |

- **GPU clock lock** `spark-gpu-clock-lock` active on every node
  (`nvidia-smi -lgc 0,2200`) — the launcher does not check it, the recover
  script does. Same service and file as the V4 Flash recipe:
  [`scripts/spark-gpu-clock-lock.service`](scripts/spark-gpu-clock-lock.service).
- Champion env (`/home/jun/dsv41-vllm/CHAMPION.env` on forge):
  ```text
  MAXLEN=430080 GMU=0.80 SEQS=8 SPEC_K=5
  DRAFT_METHOD=greedy ENGRAM_THREADS=32 MAX_BATCHED=8192
  ```

**Then:**

1. Lock clocks and verify the fabric (one IPv4 per fabric NIC, MTU 9000).
2. Launch: `env $(grep -v '^#' CHAMPION.env | xargs) bash /home/jun/launch-dsv41-vllm-tp4.sh`
   (or `bash scripts/dsv41-recover.sh` — see [after a node reboot](#after-a-node-reboot)).
   The launcher boots **disarmed**, waits for the API, runs the spec-decode
   gate, then arms `unless-stopped`.
3. Verify: `curl -s http://192.168.10.1:8000/v1/models` lists
   `deepseek-v4.1-flash`; the spec gate must have printed
   `OK: speculative decoding live`.
4. Bench: the campaign harness lives on forge under `/home/jun/dsv41-vllm/`
   (`v41bench.py`, `bench-decode.py`, `bench-depth.py`, `phase4/gates.py`).

**Serving shape** (from `launch-dsv41-vllm-tp4.sh`):

```text
--tensor-parallel-size 4 --nnodes 4
--gpu-memory-utilization 0.80 --max-model-len 430080
--max-num-seqs 8 --max-num-batched-tokens 8192
--block-size 128
--engram-config '{"cpu_offload": false}'
--speculative-config {"method":"dspark","num_speculative_tokens":5,
                      "draft_sample_method":"greedy",
                      "rejection_sample_method":"block",
                      "enable_adaptive_verification":false}
--compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE", ...}'
--tool-call-parser deepseek_v41 --enable-auto-tool-choice
--reasoning-parser deepseek_v41
--limit-mm-per-prompt '{"image":4}'
```

Note `--max-num-seqs 8` vs the advertised 4: see
[the concurrency contract](#the-concurrency-contract).

## What we had to fix (six findings)

Each item: what it was, what we changed, and who gets the credit.

### 1 · Engram-on-disk has to fit the box
V4.1 Flash's 510 GB checkpoint does not leave room to copy the engram tables
into RAM on a 128 GB GB10. We run **engram DISK mode**: every rank reads its
engram rows from local NVMe (`DSV41_ENGRAM_DISK=1`,
`DSV41_ENGRAM_DISK_THREADS=32`, chunk 16), and each rank reads weights *and*
engram rows locally — no NFS, no `ENGRAM_LOCAL` staging copy. Startup is slower,
but it fits and it is stable.
*Credit: tonyd2wild + Kai (engram-on-disk design).*

### 2 · Rank offsets in the engram partition
The engram tables must be **partitioned contiguously and distinctly** per rank,
not replicated. `engram.py`'s rank-offset fix gives rank 0/1/2/3 the layer-1
ranges `[0,96M) / [96M,192M) / [192M,288M) / [288M,384M)`. Verified on all four
ranks in the boot log; without it, ranks collide on the same rows.
*Credit: tonyd2wild + Kai (rank-offset patch).*

### 3 · Engram serial reads are the prefill bottleneck
The engram row-store reads were **serial (~300 µs/row)**, which dominates cold
prefill. 0xSero's parallel reader measures **~17 µs/row** (cached **~0.4 µs**),
and the lane's prefill goes from **6–10 tok/s to 200+ tok/s**.
**Honest note:** we did **not** build or measure our own parallel reader — the
draft `row_store.cpp` in our SGLang lane was never rebuilt or tested. We quote
0xSero's measurement, not ours.
*Credit: 0xSero (parallel Engram reader + SM120 attention fix).*

### 4 · SGLang + DSpark corrupts; vLLM + DSpark is clean
On the SGLang `dev-dsv41` lane, speculation ON deterministically corrupted
tool-result continuations (`</parameter>` / `<tool_result>` runaways, 3/3
identical md5) across a **6-config matrix** — stock, no-graph-padding, align
tier, block-size 4, SWA bounded-replay off — with spec OFF clean. The same
second-turn continuation is **byte-clean on vLLM + DSpark** across the tool
gate, corrcheck, NIAH, vision, soak, and both boots. Diagnosis moved from
"engine-agnostic / model-boundary" to **SGLang-side verify path** (consistent
with SGLang PR #38879, merged after our image was built).
*Credit: our corruption matrix (phase 1/2); LMSYS for `dev-dsv41`.*

### 5 · The DSML parser dropped parameters without `string=`
V4.1 emits DSML tool parameters **without the `string=` attribute**. SGLang's
`deepseekv32_detector.py` silently dropped those parameters, so tool calls
parsed with **empty args**. Our patch makes the attribute optional; it is
regression-verified against all three attribute states. **vLLM's
`deepseek_v41` parser does not have this bug** — no patch needed on the ship
lane, and the upstream report is SGLang-only.
*Credit: our finding + patch (phase 1); SGLang/LMSYS upstream.*

### 6 · Greedy draft is worth +30% C1
At k=5 the draft sampler was probabilistic. Switching it to **`greedy`**
(`draft_sample_method: greedy`) took C1 coding from 54.5 → **70.8 tok/s**
(+30%), math +36%, prose +31%, and C4 coding +25% — while DSpark acceptance
length stayed ~unchanged (4.36). It was the single accepted arm of the tuning
campaign; k-sweeps (k=4, k=10) and compile-fusion passes both regressed and
were rejected.
*Credit: ours (phase-4 arm B3); recipe lineage tonyd2wild + Kai.*

## After a node reboot

A single worker reboot kills the whole TP4 world: the remaining ranks hang on
the dead rank's rendezvous and the world does not self-heal. Two commands fix
it, in order.

**Manual:** on forge, `bash /home/jun/git/spark-bench/scripts/dsv41-recover.sh`.
The script (idempotent, single-instance via `flock`) verifies all four nodes are
reachable, verifies `spark-gpu-clock-lock` is active on each, stops any
`vllm_dsv41` **head-first**, waits for the GPUs to drain, relaunches from
`CHAMPION.env`, waits for `/v1/models` to list `deepseek-v4.1-flash`, then arms
`unless-stopped` on every rank. Banking on a two-node-command recovery is much
better than re-typing the champion env under pressure.

**Automatic (after the campaign):** install the drafted unit **on forge only** —
`scripts/dsv41-world.service` — which sleeps 45 s (fabric + clock-lock settle)
and then runs the same recovery script. It is a draft; the handoff is explicit
that it is not installed during the tuning campaign. Do not install it on a
worker.

**How to test it (after the campaign):** reboot one worker, wait, confirm the
world returns.

```bash
ssh anvil sudo reboot
# wait ~3-5 min for the node + clock-lock, then:
curl -s http://192.168.10.1:8000/v1/models | grep deepseek-v4.1-flash
# and on forge:
systemctl status dsv41-world.service
```

Testing waits until the tuning campaign is over — rebooting a worker mid-arm
invalidates the arm (that is exactly how B7 was invalidated at 17:50).

## The concurrency contract

The launcher and the dash disagree *by design*, and the design is now written
down:

- **Launcher `SEQS=8`** → `--max-num-seqs 8`: **admission headroom**. The engine
  may hold a small queue behind the four active slots so a new request is not
  rejected while the four slots are busy.
- **Dash `maxSeqs: 4`** (and therefore the runtime-capacity API the router
  reads): the **advertised** capacity. Four is the measured cap — C4 = 56% of
  C1 per-stream, C6 43%, C8 27% — and concurrent 100k-token prefills serialize
  TTFT (C4 at 100k depth = 4% of C1, TTFT 187 s), so the dashboard should queue
  long prompts at 2.

Both files carry the note: `config/spark-deployment.json` (live group comment)
and the DGX-dash `README.md` deployment section. **Do not** raise `maxSeqs` to 8
to "match" the launcher.

## Attribution

- **tonyd2wild + Kai** — the vLLM V4.1 recipe, engram-on-disk, SM12x patches,
  and the GB10 fast/slow-state finding (their issue #1). Repo pinned at
  `ca662ac` (boot 10).
- **0xSero** — SGLang engram adapter, SM120 attention fix, parallel Engram
  reader.
- **LMSYS** — SGLang `dev-dsv41` image.
- **vLLM team** — `dsv41-feat` branch.
- **DeepSeek** — the model (`DeepSeek-V4.1-Flash` @ `fb2764a5`).
- **Our contributions** — the arm64 multi-node port and image chain, all-local
  weights (no NFS), the greedy-draft finding (+30% C1), the SGLang DSpark
  corruption matrix, the DSML-parser bug + patch, and the arm-sweep methodology
  (one variable, ≥3 reps, drift band, gates).

## Status / open items

`TODO(final)` — this section is not publishable until the campaign freezes:

1. Stage C combo A/B/A + the **frozen** champion table → `phase4/RESULTS.md`.
2. Remaining arm verdicts (B7 batched-tokens, B4 clock unlock, B5 MoE/prefill
   backend, B8 DeepSelect, B9 NCCL sweep, B10 engram threads).
3. Final gates on the frozen champion, including the 30–60 min sustained soak
   (only 5-min soaks so far) and 400k NIAH on the final boot.
4. The depth × category honest map (5k / 10k / 50k).
5. LocalMaxxing Verified runs (`code-v1`, `reasoning-v1`).
6. Decide shipped context: 420k (current) vs 300k.

**What this is not:** not an official DeepSeek benchmark; not a V4 Flash
comparison in disguise (different model, different engine, different day); not
a "50k agent session" claim until the depth table lands; not a license to ship
prompts — weights stay on the cluster.
