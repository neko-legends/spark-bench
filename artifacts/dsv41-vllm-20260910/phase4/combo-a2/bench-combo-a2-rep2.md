## combo-a2-rep2 (2026-09-11T05:07:08Z)

phase4 arm combo-a2 rep 2

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 45.75 | 51.74 | 0.359 |
| C4 | 106.62 | 31.08 | 0.462 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 72.71 | 45.79 |
| json | 43.72 | 32.04 |
| narrative | 29.17 | 14.68 |
| prose | 34.4 | 16.42 |
| math | 73.16 | 40.52 |
| reasoning | 59.94 | 29.91 |
| summary | 34.71 | 16.72 |
| format | 66.11 | 52.58 |
| ceiling_count | 86.3 | 60.14 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
