## b7-batched16k-rep2 (2026-09-11T02:55:26Z)

phase4 arm b7-batched16k rep 2

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 42.43 | 48.08 | 0.374 |
| C4 | 105.34 | 30.9 | 0.501 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 54.72 | 47.51 |
| json | 41.93 | 31.99 |
| narrative | 20.19 | 11.07 |
| prose | 29.19 | 14.66 |
| math | 71.22 | 44.02 |
| reasoning | 56.66 | 30.68 |
| summary | 33.95 | 17.69 |
| format | 76.77 | 49.59 |
| ceiling_count | 84.7 | 42.21 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
