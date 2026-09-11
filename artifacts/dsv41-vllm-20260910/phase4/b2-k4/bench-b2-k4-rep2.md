## b2-k4-rep2 (2026-09-11T00:01:05Z)

phase4 arm b2-k4 rep 2

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 42.0 | 47.17 | 0.346 |
| C4 | 109.28 | 31.44 | 0.468 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 64.86 | 47.46 |
| json | 47.03 | 29.51 |
| narrative | 30.13 | 14.99 |
| prose | 34.63 | 16.46 |
| math | 55.4 | 40.24 |
| reasoning | 37.96 | 30.15 |
| summary | 35.35 | 18.91 |
| format | 72.01 | 53.79 |
| ceiling_count | 76.49 | 53.53 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
