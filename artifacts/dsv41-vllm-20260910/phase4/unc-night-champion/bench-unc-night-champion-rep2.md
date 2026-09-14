## unc-night-champion-rep2 (2026-09-14T05:43:05Z)

phase4 arm unc-night-champion rep 2

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 45.61 | 51.74 | 0.348 |
| C4 | 112.49 | 32.77 | 0.456 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 71.9 | 53.67 |
| json | 51.05 | 29.59 |
| narrative | 26.84 | 14.76 |
| prose | 28.76 | 18.25 |
| math | 68.94 | 46.86 |
| reasoning | 53.22 | 31.65 |
| summary | 33.45 | 18.68 |
| format | 79.78 | 48.67 |
| ceiling_count | 85.37 | 58.9 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
