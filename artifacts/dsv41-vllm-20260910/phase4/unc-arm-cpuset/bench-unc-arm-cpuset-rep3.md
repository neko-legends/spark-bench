## unc-arm-cpuset-rep3 (2026-09-14T05:05:41Z)

phase4 arm unc-arm-cpuset rep 3

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 45.13 | 50.75 | 0.332 |
| C4 | 108.09 | 31.49 | 0.502 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 74.31 | 43.83 |
| json | 43.09 | 31.71 |
| narrative | 25.56 | 14.87 |
| prose | 30.61 | 18.44 |
| math | 67.14 | 44.26 |
| reasoning | 52.66 | 28.56 |
| summary | 37.24 | 16.91 |
| format | 75.39 | 53.32 |
| ceiling_count | 84.32 | 59.83 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
