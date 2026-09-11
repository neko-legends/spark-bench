## combo-b-ttft2k (2026-09-11T04:19:11Z)

ttft2k

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 44.87 | 50.47 | 0.343 |

### Per-stream tok/s by category

| category | C1 |
|---|---|
| coding | 74.21 |
| json | 46.9 |
| narrative | 25.39 |
| prose | 30.06 |
| math | 68.79 |
| reasoning | 56.46 |
| summary | 28.69 |
| format | 73.26 |
| ceiling_count | 83.62 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 2000 | 2950 | 1.983 | 1488.0 |
