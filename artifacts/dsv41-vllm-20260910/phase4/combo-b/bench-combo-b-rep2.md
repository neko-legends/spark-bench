## combo-b-rep2 (2026-09-11T04:07:00Z)

phase4 arm combo-b rep 2

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 36.4 | 40.77 | 0.416 |
| C4 | 87.18 | 25.36 | 0.511 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 56.96 | 32.07 |
| json | 34.42 | 31.74 |
| narrative | 19.6 | 11.77 |
| prose | 26.69 | 13.79 |
| math | 61.0 | 30.29 |
| reasoning | 42.61 | 20.32 |
| summary | 26.79 | 19.85 |
| format | 58.06 | 43.05 |
| ceiling_count | 64.8 | 45.84 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
