## combo-a2-rep1 (2026-09-11T05:05:27Z)

phase4 arm combo-a2 rep 1

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 38.97 | 44.44 | 0.415 |
| C4 | 103.83 | 30.08 | 0.475 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 53.38 | 42.62 |
| json | 38.8 | 26.82 |
| narrative | 21.14 | 11.89 |
| prose | 24.68 | 17.24 |
| math | 54.68 | 40.3 |
| reasoning | 53.33 | 29.83 |
| summary | 36.42 | 15.61 |
| format | 73.1 | 56.34 |
| ceiling_count | 80.37 | 52.76 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
