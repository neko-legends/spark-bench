## unc-arm-cpuset-rep2 (2026-09-14T05:04:12Z)

phase4 arm unc-arm-cpuset rep 2

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 46.56 | 52.58 | 0.323 |
| C4 | 111.19 | 32.23 | 0.456 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 71.1 | 43.17 |
| json | 52.99 | 31.27 |
| narrative | 28.44 | 14.68 |
| prose | 31.34 | 15.68 |
| math | 65.46 | 48.45 |
| reasoning | 53.87 | 28.36 |
| summary | 36.67 | 18.29 |
| format | 80.8 | 57.94 |
| ceiling_count | 86.17 | 58.71 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
