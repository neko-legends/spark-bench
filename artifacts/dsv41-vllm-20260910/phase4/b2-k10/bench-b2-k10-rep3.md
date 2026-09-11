## b2-k10-rep3 (2026-09-10T23:29:54Z)

phase4 arm b2-k10 rep 3

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 33.55 | 37.49 | 0.388 |
| C4 | 68.37 | 19.57 | 0.53 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 59.94 | 31.21 |
| json | 27.0 | 16.11 |
| narrative | 18.17 | 9.25 |
| prose | 18.66 | 10.56 |
| math | 52.91 | 28.8 |
| reasoning | 32.78 | 18.93 |
| summary | 20.4 | 10.37 |
| format | 70.08 | 31.37 |
| ceiling_count | 95.8 | 57.53 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
