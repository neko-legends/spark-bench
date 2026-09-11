## b2-k10-rep2 (2026-09-10T23:27:46Z)

phase4 arm b2-k10 rep 2

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 34.86 | 38.82 | 0.38 |
| C4 | 73.07 | 20.7 | 0.483 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 62.07 | 29.58 |
| json | 29.65 | 14.86 |
| narrative | 19.04 | 9.31 |
| prose | 19.28 | 10.42 |
| math | 56.08 | 32.09 |
| reasoning | 37.51 | 19.81 |
| summary | 20.96 | 12.68 |
| format | 65.95 | 36.89 |
| ceiling_count | 95.01 | 61.89 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
