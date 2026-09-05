# Qwen 3.8 Flash Next — official NVIDIA NVFP4 on four DGX Sparks

## State: 2026-09-05

Current endpoint: `http://forge:8000/v1`, served ID `qwen3.8-flash-next`.
Four GB10 nodes, TP4 **plus expert parallel**, one endpoint. The GLM and
DeepSeek recipes remain separate archived lanes; they are not running alongside Qwen.
This is a first benchmark report, not a completed production qualification.

## Weights and image identity

- Checkpoint: `nvidia/Qwen3.8-Flash-Next-NVFP4`; revision prefix observed at download: `fab0aecb760c`.
- Downloaded ~132.7 GB to Forge's NVMe, then rsync over CX7 to local NVMe on every rank.
- Paths: `/home/jun/models/qwen38-flash-next-nvfp4` on each node; mounted at `/models/qwen38`.
- Fanout checks matched file counts and total bytes on all ranks. **This was not a cryptographic file-content verification.**
- Base image: `vllm/vllm-openai:qwen38-flash-next@sha256:fc120ece0a388cc0aa1caad4a9f1cd92113484ab7ec2fd0efadd62585be05bf8`.
- Patched local image: `local/qwen38-gb10:e1`.
- Built image **ID** (not a published registry manifest digest): `sha256:6fc66a65645c6d3099aba31231cc005a5074608f1f572399e98f5dfa6a6d0407`.
- Built once on Forge; docker save/load over CX7; identical image ID checked on all ranks.
- Installed vLLM identifies as `0.1.dev20073+g8e685d198`.

The patched image is local, not published. The deployment Dockerfile, vendored patches
and launcher are retained in the operator's `artifacts/qwen38-nvfp4-20260905/`
working directory. This document is not a claim that the base image alone reproduces
these results. A separately packaged, license-reviewed public build recipe remains work to do.

## Current tested launch settings

The local launcher was invoked as follows (it requires its adjacent `patches/` directory):

```bash
PLE_MODE=resident CUDAGRAPH_MODE=full MOE_BACKEND=stock GPU_MEM_UTIL=0.78 \
  bash /home/jun/launch-qwen38-tp4.sh
```

Resolved core settings:

| Setting | Value |
|---|---|
| Topology | TP4, EP enabled, 4 nodes, multiprocess executor |
| Native context | 262144; no YaRN extension |
| Sequence slots / batch token budget | 16 / 8192 |
| Memory utilization | 0.78 |
| PLE | Resident, not mmap |
| Target KV dtype | auto / bf16 |
| MTP | method `mtp`, 2 speculative tokens |
| Compilation | mode 0, FULL_DECODE_ONLY, capture sizes `[1,2,4,8]` |
| MoE backend | stock auto-selection; no explicit `--moe-backend` override |
| Prefix caching / chunked prefill | enabled |
| Vision encoder TP mode | data |
| Reasoning / tool parser | qwen3 / qwen3_coder |
| API / distributed master port | 8000 / 25100 |

The logs resolved quantization as `modelopt_mixed` for the official mixed checkpoint.
The target experts remain NVIDIA NVFP4; the checkpoint's FP8 PLE and FP8 MTP
components require separate handling. EP avoids slicing the small MoE intermediate
dimension into unsupported per-rank shapes.

The earlier trial used `PLE_MODE=mmap`, PIECEWISE graphs and memory utilization
0.80. It produced a larger KV pool but lower observed speeds. Do not force FULL
capture around the mmap CPU lookup path; that requires separate validation.

## Fabric and operational setup

Ranks: Forge, Anvil, Ember, Flame on `192.168.10.1` through `.4`, rail-B CX7,
interface `enP2p1s0f1np1`, HCA `roceP2p1s0f1`, MTU 9000. NCCL 2.30.7 is host-staged
and preloaded. Use RoCE v2, explicit fabric address range/HCA/socket interfaces,
and no fixed `NCCL_IB_GID_INDEX`. Bulk fanout originates on Forge over the wired rail.
Docker uses host networking/IPC, GPU access and nofile 1048576. Workers start before
the head. Stop existing GPU workloads and perform the UMA cache-drop preflight
before loading; don't run the launcher's destructive preflight against an active serve.

GLM-specific recovery watchdogs and cache-warming service were stopped for this
campaign. They must not resurrect GLM on Qwen's occupied devices. No Qwen-specific
production recovery policy is established by these benchmark results.

## Patch provenance and startup fixes

Sources:

- [blazux](https://github.com/blazux/qwen3.8-Flash-DGX), reviewed at `b76890d`:
  PLE mmap option, GB10 FLA/GDN fixes, Mamba state-copy/bounds and prefix-cache fixes,
  exact/deterministic QSA top-k paths; optional FP8 QSA KV support.
- [getrefined](https://github.com/getrefined/Qwen3.8-Flash-Next-NVFP4-vLLM-DGX-Spark),
  `f736930`: FP8 PLE resolver under a mixed ModelOpt parent. The base image predates
  the model-card-required PLE fix; the compatible fix was backported.
- [tsw2k quad recipe](https://github.com/tsw2k/Qwen3.8-Flash-Next-Quad-DGX-Sparks),
  `497a58e`: multi-node launch/fabric/nofile/EP guidance.
- [MiaAI dual-Spark recipe](https://github.com/MiaAI-Lab/Qwen3.8-Flash-Next-Dual-DGX-Sparks),
  `c2325b22602b51a5faf55fc2bebccc34f3f80b9f`: FP8_BLOCK_SCALES MTP-expert dispatch,
  additive MTP layer-index config aliases, vision encoder data-parallel mode.
  Patched config copies are mounted separately; downloaded weight files are unchanged.

The optional FP8 KV patch is present but **not enabled in these measurements**.
Reduced-vocabulary drafting, NFS weights and alternate checkpoints were not used.
Upstream patch licenses, including MiaAI's AGPL terms, must be retained in any
redistributed derivative recipe/image.

Local build/launcher defects fixed during bring-up:

1. Docker `/bin/sh` does not expand Bash brace lists: kernel-source COPY arguments
   were expanded explicitly.
2. JSON splitting-op quotes were lost through generated shell scripts: preserve
   quoting when serializing Docker environment values.
3. The launch check compared a name-only regex against `name + status`, falsely
   reporting a running worker dead; check names only.
4. An explicit `MOE_BACKEND=stock` sentinel omits the override. An empty value
   previously selected the shell's default `marlin` instead.
5. The checkpoint-config alias script must be staged next to the launcher.

## Measurements and their limits

See the [README table](../README.md#qwen-3-8-flash) and
[recorded summary](../results/qwen38-nvfp4-tp4-2026-09-05.json).
The [benchmark scripts](../scripts/qwen38-first-pass/) are archived as executed,
not endorsed as a finished regression suite.

- Resident C1: 400-token budgets, three runs per category/thinking mode;
  reported median. Code off: 70.3/70.0/69.6; prose off: 52.6/51.2/51.4 tok/s.
- Aggregate: one run each at C4/C8/C16, 1200 tokens per stream, temperature 0,
  thinking off, nonce-suffixed code prompts. Completed totals: 4800/9600/19200.
  End-to-end rates: 191.5/334.1/510.6 tok/s.
- MTP counters: 25062 accepted / 27496 drafted = ~91.1%, cumulative across
  that boot's traffic. Not a per-category acceptance measurement.
- KV pool: resident 4016501 tokens, 15.32× native context; mmap 5055959, 19.29×.
- The earlier mmap C1 measurements used thinking ON. Comparing its 26.3 code
  directly with resident thinking-OFF 70.0 would overstate an apples-to-apples gain.
- Do not attribute the full speed difference to one mechanism: residency,
  compilation mode and memory budget changed together. Logs of long-prefill
  mmap activity do not prove seconds of overhead per ordinary decode step.
- The aggregate harness does not fail closed on thread exceptions and has no
  interleaved baseline or per-pass isolation gate. All reported runs returned
  their requested token totals, but independent repeatability still needs testing.
- SGLang was researched only, not run. Head-topology restrictions in the inspected
  SM121 kernel and missing mixed-MTP dispatch need work before an equivalent TP4
  test. External TP2 figures are not a local SGLang-vs-vLLM comparison.

## Retrieval and remaining gates

[Resident retrieval smoke output](../results/qwen38-resident-niah-smoke-2026-09-05.jsonl)
contains nine successful needle retrievals. However, the script estimates lengths
using words/1.35 and insertion positions using characters. Its `ctx` labels are
**nominal**, not measured prompt-token lengths. They do not certify exact
4k/32k/128k context gates. The fixed repeated filler/needle is also a limited test.

Remaining: tokenizer-calibrated NIAH with varied needles and controlled cache
regimes; repeated aggregate runs with quiescence/finish validation; resident-lane
tool, thinking and vision checks under load; mixed-prefill latency; multi-hour soak
and per-rank OOM telemetry. No 1M production claim.
