## unc-night-champion-rep3 (2026-09-14T05:44:34Z)

phase4 arm unc-night-champion rep 3

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 43.76 | 49.5 | 0.349 |
| C4 | 108.61 | 31.77 | 0.492 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 73.76 | 50.91 |
| json | 42.63 | 32.51 |
| narrative | 26.64 | 14.95 |
| prose | 30.88 | 16.14 |
| math | 68.64 | 44.02 |
| reasoning | 44.17 | 27.29 |
| summary | 33.78 | 18.65 |
| format | 75.47 | 49.72 |
| ceiling_count | 86.27 | 59.02 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
