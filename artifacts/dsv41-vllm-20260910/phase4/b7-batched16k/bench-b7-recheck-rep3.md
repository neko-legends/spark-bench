## b7-recheck-rep3 (2026-09-11T03:18:12Z)



Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 45.87 | 51.64 | 0.339 |

### Per-stream tok/s by category

| category | C1 |
|---|---|
| coding | 72.23 |
| json | 43.78 |
| narrative | 29.26 |
| prose | 30.16 |
| math | 73.7 |
| reasoning | 56.88 |
| summary | 33.9 |
| format | 73.17 |
| ceiling_count | 86.65 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
