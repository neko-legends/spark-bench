## unc-arm-cpuset-rep1 (2026-09-14T05:02:41Z)

phase4 arm unc-arm-cpuset rep 1

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 45.72 | 51.57 | 0.35 |
| C4 | 112.1 | 32.51 | 0.467 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 72.85 | 50.31 |
| json | 43.69 | 30.22 |
| narrative | 26.09 | 14.88 |
| prose | 31.67 | 16.68 |
| math | 72.17 | 40.75 |
| reasoning | 55.58 | 34.09 |
| summary | 35.81 | 18.49 |
| format | 74.68 | 54.69 |
| ceiling_count | 81.71 | 59.88 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
