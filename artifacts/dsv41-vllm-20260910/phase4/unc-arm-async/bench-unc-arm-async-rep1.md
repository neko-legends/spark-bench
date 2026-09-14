## unc-arm-async-rep1 (2026-09-14T03:30:49Z)

phase4 arm unc-arm-async rep 1

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 44.85 | 50.81 | 0.35 |
| C4 | 107.1 | 31.13 | 0.485 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 72.81 | 45.87 |
| json | 48.53 | 29.09 |
| narrative | 26.7 | 15.64 |
| prose | 30.73 | 17.6 |
| math | 68.39 | 47.72 |
| reasoning | 50.4 | 27.09 |
| summary | 35.94 | 17.26 |
| format | 72.96 | 48.78 |
| ceiling_count | 82.17 | 59.04 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
