# GLM-5.3-Flash FP4 (nvidia/GLM-5.3-Flash-FP4-Local) · TensorFold Zig · four Sparks, TP-4 — 2026-10-17

The same bench as the vLLM row next door (`../glm53-fp4-vllm-20261017/`): same harnesses, frozen inputs, scoring and
thinking-off requests. Only the engine changed.

**Engine:** TensorFold Zig, branch `glm53-tensorfold-20261017` (tensorfold-4x-sparks), binary built at a83582d1. This is
upstream TensorFold's GLM CUDA family plus our FP4-Local loader: MIXED_PRECISION admit, csf_32x2_v1 scale decode, MXFP8 /
FP8_PB_WO widened to bf16, W4A16 MTP experts, a CUDA image tower, structured output and server API parity. It ran at
TP-4 over NCCL on the RoCE rail, with MTP drafts on, `--vision`, 4 streams, and a 320,000-token window per stream.
Load took 237 s; each rank holds 47.4 GiB of weights (rank 0 holds 51 GiB with the image tower).

Gates passed before this bench (GPU window, same day):
- HF per-layer gate (8 layers): cos ≥ 0.999989.
- Greedy tokens vs vLLM: 7/7, including 2 near ties that vLLM also loses against its own earlier run.
- MTP: drafted output equals undrafted output.
- Image tower: per-block cos ≥ 0.999995.

| Area | vLLM b12x (TP-4) | TensorFold Zig (TP-4) |
| --- | ---: | ---: |
| Knowledge, MMLU-200 | 88.0 % (176/200) | 88.0 % (176/200); 195/200 replies identical |
| Math, GSM8K 0–29 | 100 % | 100 % |
| Coding, 5 tasks | 80 % | 80 % |
| Instruction following, 20 | 90 % | 95 % |
| JSON schema / tools / long context to 229K tokens | 100 / 100 / 100 % | 100 / 100 / 100 % |
| Summary: facts kept / stale / invented numbers | 100 / 0 / 4.2 % | 100 / 0 / 0 % |
| Vision text, 166 strings | 166/166 | 166/166 |
| Vision shapes 30 (a3 + a5) / objects counted 23 | 28/30 / 0/23 | 28/30 / 0/23 |
| Code / prose, 1 stream (tok/s) | 82.0 / 36.5 | 58.7 / 36.8 |
| 4 streams, aggregate (tok/s) | 81.2 | 61.6 |
| TTFT, short prompt (code / prose) | 0.25 / 0.25 s | 0.17 / 0.14 s |
| Cold prompt 32K / 131K / 200K tokens | 12.3 / 50.8 / 79.4 s | 18.4 / 75.5 / 120.3 s |

The two engines agree on quality. The 1-point differences on IF and on invented numbers are single items. TensorFold
wins on time to first token and is level on prose. It is slower on code decode (−28 %), on 4 streams (−24 %) and on cold
prefill (about 1.5× slower: 1.66–1.79K tokens/s vs 2.5–2.7K). Known causes:
- The FP8 attention and dense weights are widened to bf16 as they are read, roughly 2.3 GB more read per token per rank.
- The collectives are NCCL, not our RoCE path.

Native FP8 GEMMs and the RoCE collectives are the next speed work.

Files:
- `qbench-glm53-fp4-tf-20261017.json`: 283 requests, 0 transport errors.
- `qbench-glm53-vllm-vs-tf.{md,png,svg}`: the chart's series labels were shortened in copies of the two JSONs.
- `prefill/`: from the same prefill-ladder.py (sha256 dc788a39…).
- `vision/vision-all.json`: from the same window-vision.py, with a fresh cache. `vision-live-run.jsonl` holds the per-cell rows.
