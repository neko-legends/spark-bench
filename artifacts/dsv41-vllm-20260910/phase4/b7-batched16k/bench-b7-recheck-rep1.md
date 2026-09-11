## b7-recheck-rep1 (2026-09-11T03:16:59Z)



Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 45.54 | 51.14 | 0.333 |

### Per-stream tok/s by category

| category | C1 |
|---|---|
| coding | 66.49 |
| json | 41.78 |
| narrative | 29.74 |
| prose | 33.36 |
| math | 72.43 |
| reasoning | 55.03 |
| summary | 34.72 |
| format | 75.59 |
| ceiling_count | 85.9 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
