## b3-greedy-ttft2k (2026-09-10T22:40:52Z)

ttft2k

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 39.84 | 45.56 | 0.406 |

### Per-stream tok/s by category

| category | C1 |
|---|---|
| coding | 56.72 |
| json | 31.97 |
| narrative | 24.07 |
| prose | 28.66 |
| math | 72.19 |
| reasoning | 51.47 |
| summary | 27.37 |
| format | 72.03 |
| ceiling_count | 81.41 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 2000 | 2950 | 2.937 | 1004.5 |
