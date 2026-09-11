## combo-a2-rep3 (2026-09-11T05:08:39Z)

phase4 arm combo-a2 rep 3

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 45.73 | 51.73 | 0.356 |
| C4 | 104.53 | 30.51 | 0.463 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 73.76 | 47.2 |
| json | 46.11 | 34.65 |
| narrative | 26.25 | 14.63 |
| prose | 29.14 | 18.1 |
| math | 68.96 | 43.1 |
| reasoning | 56.68 | 28.17 |
| summary | 32.97 | 17.3 |
| format | 80.0 | 40.91 |
| ceiling_count | 85.65 | 59.28 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
