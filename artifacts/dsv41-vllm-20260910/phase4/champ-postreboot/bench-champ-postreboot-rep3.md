## champ-postreboot-rep3 (2026-09-11T01:50:25Z)

phase4 arm champ-postreboot rep 3

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 46.15 | 52.35 | 0.333 |
| C4 | 107.48 | 31.53 | 0.488 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 74.3 | 44.63 |
| json | 44.01 | 30.88 |
| narrative | 23.92 | 15.16 |
| prose | 31.94 | 17.44 |
| math | 76.65 | 43.48 |
| reasoning | 54.65 | 28.06 |
| summary | 32.29 | 20.22 |
| format | 81.05 | 52.4 |
| ceiling_count | 85.68 | 60.01 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
