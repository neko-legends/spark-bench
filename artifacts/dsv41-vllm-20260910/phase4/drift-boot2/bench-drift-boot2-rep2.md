## drift-boot2-rep2 (2026-09-10T21:42:38Z)

phase4 arm drift-boot2 rep 2

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 33.12 | 37.43 | 0.478 |
| C4 | 97.67 | 28.54 | 0.549 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 49.43 | 43.62 |
| json | 36.05 | 29.41 |
| narrative | 20.39 | 16.49 |
| prose | 22.04 | 14.06 |
| math | 51.93 | 30.25 |
| reasoning | 38.9 | 26.77 |
| summary | 25.72 | 16.37 |
| format | 55.01 | 51.33 |
| ceiling_count | 81.64 | 47.46 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 8000 | 11592 | 0.388 | 29841.4 |
| 32000 | 46810 | 0.392 | 119386.5 |
