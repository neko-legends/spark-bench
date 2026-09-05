# Qwen first-pass benchmarks

Archived scripts as executed on 2026-09-05; not a finished regression suite.
They use `http://127.0.0.1:8000` and model ID `qwen3.8-flash-next`. Run on the
serving head (or deliberately adapt the endpoint), only when benchmarking is authorized.
They generate real inference traffic; do not run during an unrelated latency test.

```bash
python3 models/qwen-3.8-flash-next/benchmarks/q38_ss.py
python3 models/qwen-3.8-flash-next/benchmarks/q38_agg.py
python3 models/qwen-3.8-flash-next/benchmarks/niah.py
```

- `q38_ss.py`: greedy repetition smoke, code/prose C1, thinking off/on,
  three runs each, 400-token budgets, first-to-last-delta decode timing.
- `q38_agg.py`: code at 4/8/16 concurrent requests, thinking off,
  1200 tokens per stream, usage tokens divided by wall time.
  Thread exceptions do not reliably fail the parent process: check completed
  request/token totals, not merely its exit code.
- `niah.py`: nine fixed-needle retrieval cases. `ctx` is a word-count estimate,
  not measured token length; `s` is elapsed seconds, not tokens/second.
  This does not certify tokenizer-calibrated long-context correctness.

Save output under a new dated path in `results/`; never overwrite an earlier run.
See [methodology and remaining gates](../nvfp4-tp4/README.md).
Old paths in `scripts/qwen38-first-pass/` remain symlinks to these files.
