## b6-fusion-rep1 (2026-09-11T00:33:27Z)

phase4 arm b6-fusion rep 1

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 43.95 | 49.36 | 0.342 |
| C4 | 106.35 | 31.14 | 0.501 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 73.08 | 44.1 |
| json | 41.29 | 29.51 |
| narrative | 27.29 | 14.58 |
| prose | 28.8 | 13.31 |
| math | 63.23 | 47.7 |
| reasoning | 52.48 | 30.36 |
| summary | 32.4 | 16.39 |
| format | 76.35 | 53.15 |
| ceiling_count | 83.08 | 60.2 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
