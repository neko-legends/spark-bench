## champ-drift2-rep1 (2026-09-11T02:25:17Z)

phase4 arm champ-drift2 rep 1

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 39.42 | 44.31 | 0.414 |
| C4 | 94.01 | 27.51 | 0.513 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 68.78 | 38.33 |
| json | 40.82 | 26.25 |
| narrative | 29.3 | 12.22 |
| prose | 32.06 | 17.15 |
| math | 55.42 | 39.89 |
| reasoning | 42.55 | 29.43 |
| summary | 26.57 | 16.33 |
| format | 58.98 | 40.48 |
| ceiling_count | 63.32 | 43.6 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
