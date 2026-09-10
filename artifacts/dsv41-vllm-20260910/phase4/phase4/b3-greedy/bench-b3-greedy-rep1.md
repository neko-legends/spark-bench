## b3-greedy-rep1 (2026-09-10T22:27:04Z)

phase4 arm b3-greedy rep 1

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 42.36 | 47.51 | 0.347 |
| C4 | 104.52 | 30.79 | 0.466 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 61.44 | 47.18 |
| json | 44.4 | 32.41 |
| narrative | 23.64 | 14.64 |
| prose | 26.11 | 15.93 |
| math | 72.93 | 39.01 |
| reasoning | 49.28 | 28.41 |
| summary | 30.54 | 17.04 |
| format | 71.75 | 51.67 |
| ceiling_count | 81.71 | 59.21 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
