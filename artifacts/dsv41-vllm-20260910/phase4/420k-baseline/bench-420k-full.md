## 420k-full (2026-09-10T20:33:26Z)

420k baseline full bench

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 29.32 | 32.77 | 0.495 |
| C2 | 51.78 | 30.16 | 0.539 |
| C3 | 87.66 | 33.73 | 0.446 |
| C4 | 103.76 | 30.0 | 0.469 |
| C5 | 123.92 | 28.6 | 0.497 |
| C6 | 138.96 | 27.1 | 0.545 |

### Per-stream tok/s by category

| category | C1 | C2 | C3 | C4 | C5 | C6 |
|---|---|---|---|---|---|---|
| coding | 44.91 | 37.99 | 47.26 | 45.72 | 41.51 | 38.17 |
| json | 27.96 | 20.59 | 30.82 | 29.35 | 24.14 | 25.26 |
| narrative | 17.56 | 12.97 | 18.2 | 14.22 | 13.49 | 12.41 |
| prose | 22.1 | 15.76 | 18.51 | 17.16 | 17.01 | 15.05 |
| math | 44.16 | 37.35 | 45.98 | 43.04 | 37.77 | 37.27 |
| reasoning | 36.94 | 29.09 | 32.16 | 27.65 | 26.58 | 25.2 |
| summary | 22.55 | 23.78 | 19.82 | 17.94 | 16.48 | 16.26 |
| format | 45.94 | 63.77 | 57.07 | 44.94 | 51.83 | 47.14 |
| ceiling_count | 50.97 | 67.15 | 63.9 | 56.56 | 58.13 | 52.77 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 2000 | 2950 | 1.974 | 1494.1 |
| 8000 | 11592 | 7.621 | 1521.1 |
| 32000 | 46810 | 30.803 | 1519.6 |
| 64000 | 93335 | 64.508 | 1446.9 |
| 100000 | 145504 | 122.68 | 1186.0 |
