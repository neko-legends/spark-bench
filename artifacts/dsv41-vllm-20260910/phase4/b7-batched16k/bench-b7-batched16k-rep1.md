## b7-batched16k-rep1 (2026-09-11T02:53:40Z)

phase4 arm b7-batched16k rep 1

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 38.8 | 43.56 | 0.412 |
| C4 | 92.12 | 26.82 | 0.513 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 70.55 | 33.08 |
| json | 44.95 | 20.52 |
| narrative | 25.84 | 11.6 |
| prose | 32.49 | 14.09 |
| math | 52.24 | 42.95 |
| reasoning | 40.38 | 26.57 |
| summary | 25.87 | 15.55 |
| format | 56.18 | 50.2 |
| ceiling_count | 61.24 | 55.91 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
