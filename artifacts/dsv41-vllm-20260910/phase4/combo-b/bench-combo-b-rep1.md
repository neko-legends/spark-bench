## combo-b-rep1 (2026-09-11T04:05:14Z)

phase4 arm combo-b rep 1

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 38.25 | 42.75 | 0.382 |
| C4 | 90.01 | 25.75 | 0.499 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 65.04 | 33.7 |
| json | 43.58 | 32.24 |
| narrative | 21.83 | 13.8 |
| prose | 27.28 | 14.01 |
| math | 61.79 | 30.2 |
| reasoning | 39.26 | 24.35 |
| summary | 30.03 | 16.53 |
| format | 53.18 | 41.14 |
| ceiling_count | 61.27 | 49.73 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
