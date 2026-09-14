## unc-arm-async-rep3 (2026-09-14T03:33:49Z)

phase4 arm unc-arm-async rep 3

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 45.66 | 51.56 | 0.336 |
| C4 | 110.18 | 31.89 | 0.461 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 71.55 | 46.97 |
| json | 46.25 | 26.22 |
| narrative | 26.45 | 14.79 |
| prose | 30.92 | 18.15 |
| math | 69.89 | 41.74 |
| reasoning | 55.27 | 30.65 |
| summary | 33.08 | 17.32 |
| format | 79.11 | 59.31 |
| ceiling_count | 86.13 | 59.26 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
