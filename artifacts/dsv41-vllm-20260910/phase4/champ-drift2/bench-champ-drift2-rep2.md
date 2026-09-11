## champ-drift2-rep2 (2026-09-11T02:27:00Z)

phase4 arm champ-drift2 rep 2

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 44.45 | 49.91 | 0.332 |
| C4 | 99.79 | 29.43 | 0.48 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 68.04 | 34.37 |
| json | 43.29 | 31.55 |
| narrative | 24.75 | 14.42 |
| prose | 31.66 | 16.86 |
| math | 70.72 | 41.24 |
| reasoning | 53.53 | 27.44 |
| summary | 32.54 | 18.79 |
| format | 74.74 | 50.8 |
| ceiling_count | 63.32 | 57.11 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
