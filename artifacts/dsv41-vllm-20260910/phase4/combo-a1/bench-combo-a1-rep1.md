## combo-a1-rep1 (2026-09-11T03:39:42Z)

phase4 arm combo-a1 rep 1

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 39.85 | 45.39 | 0.407 |
| C4 | 87.5 | 24.78 | 0.565 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 69.28 | 36.4 |
| json | 38.58 | 20.76 |
| narrative | 17.76 | 13.25 |
| prose | 24.29 | 16.62 |
| math | 50.46 | 39.83 |
| reasoning | 51.98 | 26.07 |
| summary | 34.69 | 12.08 |
| format | 76.08 | 33.24 |
| ceiling_count | 82.18 | 39.41 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
