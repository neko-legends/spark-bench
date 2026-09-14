## unc-arm-async-rep2 (2026-09-14T03:32:21Z)

phase4 arm unc-arm-async rep 2

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 47.29 | 54.09 | 0.346 |
| C4 | 106.95 | 31.36 | 0.455 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 75.16 | 47.05 |
| json | 57.96 | 28.83 |
| narrative | 27.57 | 14.83 |
| prose | 29.91 | 17.12 |
| math | 69.86 | 41.95 |
| reasoning | 56.64 | 27.85 |
| summary | 37.43 | 18.65 |
| format | 78.22 | 54.63 |
| ceiling_count | 86.12 | 59.02 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
