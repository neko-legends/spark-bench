## unc-night-champion-ttft2k (2026-09-14T05:54:12Z)

ttft2k

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 44.16 | 49.71 | 0.358 |

### Per-stream tok/s by category

| category | C1 |
|---|---|
| coding | 66.86 |
| json | 41.36 |
| narrative | 26.05 |
| prose | 31.63 |
| math | 71.16 |
| reasoning | 54.73 |
| summary | 33.84 |
| format | 72.05 |
| ceiling_count | 85.76 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 2000 | 2950 | 1.904 | 1549.3 |
