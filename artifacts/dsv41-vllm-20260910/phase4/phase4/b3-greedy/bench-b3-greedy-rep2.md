## b3-greedy-rep2 (2026-09-10T22:28:40Z)

phase4 arm b3-greedy rep 2

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 45.5 | 51.14 | 0.335 |
| C4 | 106.8 | 31.03 | 0.459 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 70.78 | 49.25 |
| json | 43.79 | 27.33 |
| narrative | 25.41 | 14.25 |
| prose | 33.14 | 18.74 |
| math | 74.31 | 39.89 |
| reasoning | 55.02 | 25.01 |
| summary | 29.01 | 17.91 |
| format | 77.64 | 55.84 |
| ceiling_count | 78.93 | 57.63 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
