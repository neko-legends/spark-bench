## b6-fusion-rep3 (2026-09-11T00:36:37Z)

phase4 arm b6-fusion rep 3

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 45.81 | 52.66 | 0.368 |
| C4 | 96.04 | 27.88 | 0.538 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 72.28 | 35.44 |
| json | 48.31 | 28.85 |
| narrative | 21.58 | 14.87 |
| prose | 27.6 | 18.17 |
| math | 76.96 | 34.82 |
| reasoning | 61.15 | 21.05 |
| summary | 33.93 | 15.09 |
| format | 79.44 | 54.72 |
| ceiling_count | 86.01 | 59.9 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
