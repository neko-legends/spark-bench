## champ-drift2-ttft2k (2026-09-11T02:39:06Z)

ttft2k

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 44.5 | 50.08 | 0.337 |

### Per-stream tok/s by category

| category | C1 |
|---|---|
| coding | 73.54 |
| json | 42.88 |
| narrative | 28.04 |
| prose | 29.95 |
| math | 68.62 |
| reasoning | 50.36 |
| summary | 29.68 |
| format | 77.55 |
| ceiling_count | 86.26 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 2000 | 2950 | 1.953 | 1510.5 |
