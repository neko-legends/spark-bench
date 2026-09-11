## b2-k4-ttft2k (2026-09-11T00:12:52Z)

ttft2k

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 43.92 | 48.94 | 0.331 |

### Per-stream tok/s by category

| category | C1 |
|---|---|
| coding | 65.76 |
| json | 46.18 |
| narrative | 28.05 |
| prose | 33.97 |
| math | 63.89 |
| reasoning | 48.32 |
| summary | 38.51 |
| format | 66.81 |
| ceiling_count | 74.26 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 2000 | 2950 | 1.98 | 1489.7 |
