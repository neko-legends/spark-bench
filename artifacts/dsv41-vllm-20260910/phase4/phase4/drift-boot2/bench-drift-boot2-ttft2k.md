## drift-boot2-ttft2k (2026-09-10T21:52:32Z)

ttft2k

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 46.33 | 52.32 | 0.344 |

### Per-stream tok/s by category

| category | C1 |
|---|---|
| coding | 75.7 |
| json | 46.13 |
| narrative | 28.62 |
| prose | 34.72 |
| math | 66.05 |
| reasoning | 56.51 |
| summary | 32.63 |
| format | 78.23 |
| ceiling_count | 81.85 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 2000 | 2950 | 2.078 | 1420.0 |
