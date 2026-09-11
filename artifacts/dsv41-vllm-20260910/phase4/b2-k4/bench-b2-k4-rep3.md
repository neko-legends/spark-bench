## b2-k4-rep3 (2026-09-11T00:02:39Z)

phase4 arm b2-k4 rep 3

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 42.33 | 47.34 | 0.355 |
| C4 | 98.05 | 28.21 | 0.52 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 58.46 | 41.95 |
| json | 38.84 | 25.98 |
| narrative | 26.61 | 13.47 |
| prose | 34.61 | 19.92 |
| math | 69.27 | 38.11 |
| reasoning | 49.5 | 28.8 |
| summary | 32.49 | 17.93 |
| format | 68.95 | 39.56 |
| ceiling_count | 76.94 | 53.49 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
