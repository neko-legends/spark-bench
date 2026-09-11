## b2-k10-rep1 (2026-09-10T23:25:36Z)

phase4 arm b2-k10 rep 1

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 33.7 | 38.18 | 0.413 |
| C4 | 71.9 | 20.56 | 0.534 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 58.46 | 31.45 |
| json | 27.03 | 16.54 |
| narrative | 19.36 | 9.04 |
| prose | 20.26 | 9.71 |
| math | 52.45 | 33.7 |
| reasoning | 38.29 | 19.1 |
| summary | 21.8 | 12.34 |
| format | 67.78 | 32.58 |
| ceiling_count | 96.3 | 59.44 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
