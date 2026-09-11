## b10-engram64-rep2 (2026-09-11T05:54:05Z)

phase4 arm b10-engram64 rep 2

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 44.45 | 50.13 | 0.353 |
| C4 | 105.13 | 30.46 | 0.476 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 64.28 | 38.8 |
| json | 51.47 | 30.46 |
| narrative | 27.69 | 14.91 |
| prose | 28.87 | 17.67 |
| math | 69.7 | 46.49 |
| reasoning | 56.71 | 27.17 |
| summary | 30.29 | 17.71 |
| format | 72.02 | 50.49 |
| ceiling_count | 84.75 | 60.27 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
