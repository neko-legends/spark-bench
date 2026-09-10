# DeepSeek-V4.1-Flash on 4× DGX Spark — working artifacts (2026-09-10)

Snapshot of everything needed to reproduce the serving world and the phase-1/2/3 results.
Written to the repo as a backup while the tuning campaign (phase 4) runs; the curated
README section lands when the campaign finishes.

- `launch/launch-dsv41-vllm-tp4.sh` — vLLM TP4 launcher (Tony boot-10 config translated to our fabric; disarmed boot → API → spec gate → arm).
- `patches/` — the 8 bind-mounted vLLM patch files (md5s match tonyd2wild `patch/README.md` @ ca662ac).
- `bench/` — phase-3 bench outputs at 131k (Tony-comparable prompt set v1; our bench-decode/bench-depth).
- `gpuflip/`, `nccl/` — GB10 slow-state probes (all fast, zero flips) and 4-node all-reduce latency.
- `STATUS-phase3.md`, `STATUS-sglang-phases1-2.md` — stage-by-stage logs.
- `sglang-lane/` — the SGLang fallback (spec-off, correct, ~13 tok/s): launcher, Dockerfile (dev-dsv41 + 0xSero adapter + DSML parser fix), and the DSpark-corruption repro matrix (6 configs, all corrupt; clean on vLLM).

Model: `deepseek-ai/DeepSeek-V4.1-Flash` @ `fb2764a5`, 510 GB, local on every node.
Engine image: `local/vllm-dsv41:overlay5` (node-local builds; vLLM `dsv41-feat` @ e47aa780 on `vllm/vllm-openai:nightly-8a728663`, FlashInfer 0.7.0rc1 07869c61, prebuilt sm120 kernels).

Attribution: tonyd2wild + Kai (vLLM recipe, engram-on-disk, SM12x patches, slow-state finding), 0xSero (SGLang adapter, SM120 attention fix), LMSYS (dev-dsv41), vLLM team (dsv41-feat), DeepSeek (model).
