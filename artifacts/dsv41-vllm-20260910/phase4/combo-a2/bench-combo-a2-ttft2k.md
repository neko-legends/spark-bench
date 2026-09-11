## combo-a2-ttft2k (2026-09-11T05:18:47Z)

ttft2k

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 45.23 | 51.23 | 0.355 |

### Per-stream tok/s by category

| category | C1 |
|---|---|
| coding | 69.37 |
| json | 40.36 |
| narrative | 29.28 |
| prose | 30.54 |
| math | 76.23 |
| reasoning | 52.94 |
| summary | 35.7 |
| format | 75.44 |
| ceiling_count | 85.65 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 2000 | 2950 | 2.029 | 1453.8 |
