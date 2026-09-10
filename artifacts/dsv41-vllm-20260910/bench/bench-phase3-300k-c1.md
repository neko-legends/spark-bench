## phase3-300k-c1 (2026-09-10T20:00:04Z)

300k boot, boot-to-boot drift check vs 131k

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 43.04 | 48.71 | 0.379 |

### Per-stream tok/s by category

| category | C1 |
|---|---|
| coding | 72.97 |
| json | 42.61 |
| narrative | 23.07 |
| prose | 28.86 |
| math | 71.21 |
| reasoning | 51.71 |
| summary | 27.99 |
| format | 71.24 |
| ceiling_count | 82.11 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
