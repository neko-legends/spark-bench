## unc-night-champion-rep1 (2026-09-14T05:41:32Z)

phase4 arm unc-night-champion rep 1

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 43.62 | 49.16 | 0.354 |
| C4 | 102.14 | 29.55 | 0.476 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 68.07 | 39.06 |
| json | 42.44 | 28.29 |
| narrative | 25.8 | 14.63 |
| prose | 32.07 | 16.99 |
| math | 73.51 | 45.54 |
| reasoning | 47.8 | 27.7 |
| summary | 32.93 | 18.23 |
| format | 70.67 | 45.96 |
| ceiling_count | 79.58 | 55.82 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
