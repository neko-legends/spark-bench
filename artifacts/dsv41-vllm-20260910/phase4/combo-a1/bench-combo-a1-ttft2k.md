## combo-a1-ttft2k (2026-09-11T03:54:13Z)

ttft2k

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 35.06 | 39.36 | 0.431 |

### Per-stream tok/s by category

| category | C1 |
|---|---|
| coding | 57.66 |
| json | 34.58 |
| narrative | 22.7 |
| prose | 24.46 |
| math | 49.81 |
| reasoning | 40.79 |
| summary | 26.04 |
| format | 58.87 |
| ceiling_count | 77.5 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 2000 | 2950 | 2.097 | 1406.5 |
