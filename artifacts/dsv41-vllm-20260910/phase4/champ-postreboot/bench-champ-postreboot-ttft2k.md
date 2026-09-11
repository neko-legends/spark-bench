## champ-postreboot-ttft2k (2026-09-11T01:58:08Z)

ttft2k

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 42.59 | 47.59 | 0.357 |

### Per-stream tok/s by category

| category | C1 |
|---|---|
| coding | 67.74 |
| json | 42.02 |
| narrative | 28.88 |
| prose | 30.97 |
| math | 71.45 |
| reasoning | 55.54 |
| summary | 26.55 |
| format | 57.57 |
| ceiling_count | 64.94 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 2000 | 2950 | 2.62 | 1125.8 |
