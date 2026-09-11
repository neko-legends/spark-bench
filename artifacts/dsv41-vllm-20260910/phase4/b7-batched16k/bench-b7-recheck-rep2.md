## b7-recheck-rep2 (2026-09-11T03:17:35Z)



Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 44.46 | 49.93 | 0.329 |

### Per-stream tok/s by category

| category | C1 |
|---|---|
| coding | 73.69 |
| json | 43.71 |
| narrative | 27.92 |
| prose | 28.29 |
| math | 64.47 |
| reasoning | 50.74 |
| summary | 31.8 |
| format | 78.82 |
| ceiling_count | 86.25 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
