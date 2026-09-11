## b6-fusion-rep2 (2026-09-11T00:35:01Z)

phase4 arm b6-fusion rep 2

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 45.47 | 51.04 | 0.343 |
| C4 | 97.22 | 28.47 | 0.565 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 75.87 | 32.8 |
| json | 41.32 | 26.72 |
| narrative | 26.7 | 14.17 |
| prose | 31.92 | 15.6 |
| math | 71.73 | 40.89 |
| reasoning | 55.47 | 29.36 |
| summary | 31.76 | 19.14 |
| format | 73.56 | 49.07 |
| ceiling_count | 84.69 | 59.19 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
