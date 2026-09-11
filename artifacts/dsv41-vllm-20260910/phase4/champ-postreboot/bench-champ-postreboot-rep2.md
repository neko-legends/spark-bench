## champ-postreboot-rep2 (2026-09-11T01:48:56Z)

phase4 arm champ-postreboot rep 2

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 45.92 | 51.9 | 0.338 |
| C4 | 106.87 | 31.0 | 0.464 |

### Per-stream tok/s by category

| category | C1 | C4 |
|---|---|---|
| coding | 69.21 | 46.18 |
| json | 46.53 | 26.75 |
| narrative | 27.33 | 15.28 |
| prose | 32.91 | 19.02 |
| math | 72.59 | 42.28 |
| reasoning | 55.02 | 27.6 |
| summary | 34.8 | 20.18 |
| format | 76.81 | 50.69 |
| ceiling_count | 85.51 | 60.08 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
