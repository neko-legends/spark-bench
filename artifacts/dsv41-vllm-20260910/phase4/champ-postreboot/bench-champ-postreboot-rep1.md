## champ-postreboot-rep1 (2026-09-11T01:47:26Z)

phase4 arm champ-postreboot rep 1

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 44.79 | 50.67 | 0.35 |
| C4 | 104.34 | 30.53 | 0.485 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 69.94 | 48.67 |
| json | 43.48 | 31.04 |
| narrative | 29.8 | 15.23 |
| prose | 32.17 | 16.06 |
| math | 67.05 | 41.65 |
| reasoning | 51.33 | 30.34 |
| summary | 36.11 | 18.15 |
| format | 75.49 | 43.12 |
| ceiling_count | 86.7 | 55.19 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
