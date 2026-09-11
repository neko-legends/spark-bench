## b2-k10-ttft2k (2026-09-10T23:41:52Z)

ttft2k

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 24.83 | 27.44 | 0.472 |

### Per-stream tok/s by category

| category | C1 |
|---|---|
| coding | 41.04 |
| json | 19.36 |
| narrative | 14.01 |
| prose | 15.54 |
| math | 37.91 |
| reasoning | 27.59 |
| summary | 15.74 |
| format | 48.3 |
| ceiling_count | 73.17 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 2000 | 2950 | 2.92 | 1010.3 |
