## combo-a1-rep2 (2026-09-11T03:41:30Z)

phase4 arm combo-a1 rep 2

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 37.61 | 42.83 | 0.422 |
| C4 | 108.59 | 31.55 | 0.501 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 52.56 | 47.96 |
| json | 38.64 | 29.84 |
| narrative | 18.88 | 14.44 |
| prose | 24.32 | 14.96 |
| math | 52.53 | 45.94 |
| reasoning | 50.95 | 27.21 |
| summary | 30.23 | 16.47 |
| format | 74.49 | 55.6 |
| ceiling_count | 84.47 | 58.76 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
