## drift-boot2-rep3 (2026-09-10T21:44:30Z)

phase4 arm drift-boot2 rep 3

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 39.91 | 45.36 | 0.409 |
| C4 | 100.39 | 29.2 | 0.486 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 54.51 | 37.72 |
| json | 34.22 | 27.38 |
| narrative | 20.4 | 11.33 |
| prose | 29.85 | 12.52 |
| math | 66.42 | 44.02 |
| reasoning | 47.17 | 29.57 |
| summary | 32.76 | 17.15 |
| format | 77.52 | 53.9 |
| ceiling_count | 81.82 | 56.57 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 8000 | 11592 | 0.402 | 28800.3 |
| 32000 | 46810 | 0.445 | 105227.1 |
