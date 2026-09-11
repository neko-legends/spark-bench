## b10-engram64-ttft2k (2026-09-11T06:05:25Z)

ttft2k

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 41.98 | 47.0 | 0.349 |

### Per-stream tok/s by category

| category | C1 |
|---|---|
| coding | 62.01 |
| json | 32.91 |
| narrative | 23.96 |
| prose | 31.93 |
| math | 71.12 |
| reasoning | 51.75 |
| summary | 29.2 |
| format | 73.15 |
| ceiling_count | 84.22 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 2000 | 2950 | 6.277 | 470.0 |
