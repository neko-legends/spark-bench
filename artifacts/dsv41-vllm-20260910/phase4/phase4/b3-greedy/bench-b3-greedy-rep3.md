## b3-greedy-rep3 (2026-09-10T22:30:13Z)

phase4 arm b3-greedy rep 3

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 45.04 | 51.14 | 0.347 |
| C4 | 97.26 | 28.48 | 0.487 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 75.14 | 43.87 |
| json | 54.25 | 31.71 |
| narrative | 27.77 | 14.76 |
| prose | 29.12 | 16.75 |
| math | 59.55 | 35.82 |
| reasoning | 48.65 | 25.12 |
| summary | 35.19 | 18.6 |
| format | 79.47 | 41.2 |
| ceiling_count | 75.71 | 44.55 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
