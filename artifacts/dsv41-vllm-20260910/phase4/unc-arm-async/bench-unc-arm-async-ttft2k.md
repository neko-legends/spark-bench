## unc-arm-async-ttft2k (2026-09-14T03:38:06Z)

ttft2k

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 45.01 | 50.74 | 0.333 |

### Per-stream tok/s by category

| category | C1 |
|---|---|
| coding | 73.73 |
| json | 44.32 |
| narrative | 28.22 |
| prose | 28.68 |
| math | 67.24 |
| reasoning | 50.92 |
| summary | 38.0 |
| format | 74.8 |
| ceiling_count | 80.56 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 2000 | 2950 | 1.969 | 1498.4 |
