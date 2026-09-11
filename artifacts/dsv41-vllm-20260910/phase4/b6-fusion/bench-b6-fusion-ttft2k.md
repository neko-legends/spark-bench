## b6-fusion-ttft2k (2026-09-11T00:48:04Z)

ttft2k

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 38.23 | 42.96 | 0.382 |

### Per-stream tok/s by category

| category | C1 |
|---|---|
| coding | 69.14 |
| json | 52.66 |
| narrative | 24.2 |
| prose | 25.77 |
| math | 54.19 |
| reasoning | 38.71 |
| summary | 24.0 |
| format | 55.04 |
| ceiling_count | 63.3 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 2000 | 2950 | 3.175 | 929.1 |
