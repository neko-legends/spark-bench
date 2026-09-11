## b7-batched16k-ttft2k (2026-09-11T03:07:44Z)

ttft2k

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 37.42 | 42.51 | 0.416 |

### Per-stream tok/s by category

| category | C1 |
|---|---|
| coding | 54.55 |
| json | 39.24 |
| narrative | 22.17 |
| prose | 26.3 |
| math | 50.84 |
| reasoning | 42.39 |
| summary | 28.84 |
| format | 75.75 |
| ceiling_count | 86.48 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 2000 | 2950 | 2.275 | 1296.5 |
