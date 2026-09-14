## unc-arm-cpuset-ttft2k (2026-09-14T05:25:27Z)

ttft2k

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 45.47 | 51.14 | 0.344 |

### Per-stream tok/s by category

| category | C1 |
|---|---|
| coding | 71.22 |
| json | 50.4 |
| narrative | 27.76 |
| prose | 30.3 |
| math | 71.17 |
| reasoning | 55.98 |
| summary | 34.03 |
| format | 68.24 |
| ceiling_count | 86.39 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 2000 | 2950 | 1.836 | 1606.4 |
