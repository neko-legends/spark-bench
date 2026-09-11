## champ-drift2-rep3 (2026-09-11T02:28:36Z)

phase4 arm champ-drift2 rep 3

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 43.51 | 48.77 | 0.352 |
| C4 | 106.03 | 31.16 | 0.466 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 71.31 | 42.63 |
| json | 48.72 | 32.81 |
| narrative | 24.66 | 12.85 |
| prose | 34.0 | 19.87 |
| math | 70.94 | 47.91 |
| reasoning | 52.66 | 27.65 |
| summary | 28.12 | 18.45 |
| format | 59.77 | 47.07 |
| ceiling_count | 70.01 | 59.12 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
