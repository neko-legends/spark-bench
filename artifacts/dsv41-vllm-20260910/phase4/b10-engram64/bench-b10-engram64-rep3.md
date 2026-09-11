## b10-engram64-rep3 (2026-09-11T05:55:39Z)

phase4 arm b10-engram64 rep 3

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 45.31 | 51.24 | 0.33 |
| C4 | 110.0 | 31.93 | 0.481 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 71.59 | 43.98 |
| json | 58.08 | 30.98 |
| narrative | 26.44 | 13.82 |
| prose | 28.96 | 18.01 |
| math | 69.22 | 45.09 |
| reasoning | 52.46 | 30.16 |
| summary | 27.05 | 18.21 |
| format | 76.14 | 55.22 |
| ceiling_count | 85.34 | 42.8 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
