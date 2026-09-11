## combo-b-rep3 (2026-09-11T04:08:53Z)

phase4 arm combo-b rep 3

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 46.87 | 53.46 | 0.346 |
| C4 | 107.21 | 31.28 | 0.444 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 64.25 | 40.27 |
| json | 60.43 | 34.49 |
| narrative | 25.9 | 14.49 |
| prose | 34.64 | 18.62 |
| math | 75.24 | 39.57 |
| reasoning | 56.38 | 28.57 |
| summary | 33.78 | 21.45 |
| format | 77.08 | 52.8 |
| ceiling_count | 86.28 | 59.09 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
