## b10-engram64-rep1 (2026-09-11T05:52:27Z)

phase4 arm b10-engram64 rep 1

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 41.88 | 46.94 | 0.387 |
| C4 | 97.43 | 28.43 | 0.493 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 71.38 | 31.2 |
| json | 44.17 | 22.73 |
| narrative | 26.15 | 15.3 |
| prose | 34.95 | 17.28 |
| math | 68.55 | 38.83 |
| reasoning | 50.96 | 26.62 |
| summary | 25.39 | 18.15 |
| format | 53.96 | 57.33 |
| ceiling_count | 60.52 | 57.8 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
