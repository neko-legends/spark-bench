## b7-batched16k-rep3 (2026-09-11T02:57:08Z)

phase4 arm b7-batched16k rep 3

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 40.23 | 45.0 | 0.382 |
| C4 | 99.42 | 29.12 | 0.504 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 56.83 | 47.56 |
| json | 32.74 | 31.37 |
| narrative | 23.02 | 11.97 |
| prose | 31.74 | 14.59 |
| math | 73.3 | 31.8 |
| reasoning | 56.14 | 29.38 |
| summary | 27.07 | 17.56 |
| format | 59.19 | 48.76 |
| ceiling_count | 74.47 | 59.64 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
