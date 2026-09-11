## final-champion (2026-09-11T04:19:56Z)

Stage C final champion (greedy + B7 16k)

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 45.12 | 50.47 | 0.337 |
| C2 | 73.6 | 41.85 | 0.382 |
| C3 | 90.44 | 34.23 | 0.428 |
| C4 | 109.41 | 31.61 | 0.47 |
| C5 | 125.03 | 28.96 | 0.519 |
| C6 | 136.69 | 26.84 | 0.573 |

### Per-stream tok/s by category

| category | C1 | C2 | C3 | C4 | C5 | C6 |
|---|---|---|---|---|---|---|
| coding | 71.44 | 64.85 | 52.77 | 47.04 | 41.5 | 38.61 |
| json | 45.26 | 37.57 | 29.31 | 29.63 | 26.0 | 26.19 |
| narrative | 27.68 | 21.62 | 18.73 | 14.94 | 12.9 | 13.0 |
| prose | 31.7 | 24.44 | 18.5 | 17.29 | 15.52 | 15.27 |
| math | 69.95 | 53.42 | 44.78 | 47.18 | 38.39 | 36.97 |
| reasoning | 58.57 | 40.53 | 34.23 | 28.41 | 28.53 | 24.61 |
| summary | 27.92 | 27.5 | 19.2 | 19.39 | 16.23 | 15.48 |
| format | 71.21 | 64.86 | 56.35 | 49.01 | 52.65 | 44.61 |
| ceiling_count | 83.22 | 77.93 | 66.35 | 60.65 | 55.96 | 52.8 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 2000 | 2950 | 1.778 | 1659.3 |
| 8000 | 11592 | 7.847 | 1477.3 |
| 32000 | 46810 | 31.313 | 1494.9 |
| 64000 | 93335 | 65.216 | 1431.2 |
| 100000 | 145504 | 102.783 | 1415.6 |
