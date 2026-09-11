## combo-a1-rep3 (2026-09-11T03:43:10Z)

phase4 arm combo-a1 rep 3

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 42.42 | 47.64 | 0.384 |
| C4 | 110.09 | 32.35 | 0.485 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 72.62 | 48.09 |
| json | 41.68 | 32.02 |
| narrative | 29.93 | 13.77 |
| prose | 30.01 | 18.17 |
| math | 67.19 | 42.17 |
| reasoning | 42.9 | 27.96 |
| summary | 29.13 | 17.91 |
| format | 67.69 | 58.68 |
| ceiling_count | 71.6 | 58.35 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
