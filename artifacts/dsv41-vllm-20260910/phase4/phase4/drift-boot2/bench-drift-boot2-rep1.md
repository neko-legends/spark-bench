## drift-boot2-rep1 (2026-09-10T21:39:22Z)

phase4 arm drift-boot2 rep 1

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 37.34 | 42.28 | 0.434 |
| C4 | 83.33 | 24.29 | 0.624 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 66.96 | 32.6 |
| json | 45.07 | 19.92 |
| narrative | 25.25 | 12.85 |
| prose | 22.24 | 15.97 |
| math | 53.84 | 41.71 |
| reasoning | 38.7 | 24.39 |
| summary | 25.97 | 12.85 |
| format | 60.25 | 34.04 |
| ceiling_count | 58.14 | 38.64 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 8000 | 11592 | 19.721 | 587.8 |
| 32000 | 46810 | 62.152 | 753.1 |
