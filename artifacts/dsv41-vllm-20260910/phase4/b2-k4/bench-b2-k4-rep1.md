## b2-k4-rep1 (2026-09-10T23:59:33Z)

phase4 arm b2-k4 rep 1

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 44.31 | 49.65 | 0.345 |
| C4 | 100.64 | 28.75 | 0.501 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 64.89 | 46.93 |
| json | 45.76 | 23.26 |
| narrative | 32.52 | 14.95 |
| prose | 33.67 | 17.96 |
| math | 65.79 | 36.84 |
| reasoning | 50.9 | 24.78 |
| summary | 35.56 | 18.22 |
| format | 68.13 | 47.02 |
| ceiling_count | 73.43 | 54.66 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
