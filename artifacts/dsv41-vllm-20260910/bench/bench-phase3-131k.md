## phase3-131k (2026-09-10T18:49:26Z)

our fabric, MAXLEN=131072, DSpark k=5, FULL_AND_PIECEWISE, gmu 0.80, Tony boot10 recipe

Prompt set `v1` (identical across boots), temperature 0, thinking off. Tokens from the server's usage block; TTFT = first token delta.

### Throughput by concurrency (8 categories; the counting ceiling is excluded)

| C | aggregate tok/s | per-stream tok/s | mean TTFT (s) |
|---|---|---|---|
| C1 | 42.96 | 48.24 | 0.377 |
| C2 | 67.31 | 38.69 | 0.463 |
| C3 | 80.5 | 30.89 | 0.472 |
| C4 | 108.66 | 31.39 | 0.453 |
| C5 | 124.54 | 29.48 | 0.741 |
| C6 | 132.01 | 25.77 | 0.515 |

### Per-stream tok/s by category

| category | C1 | C2 | C3 | C4 | C5 | C6 |
|---|---|---|---|---|---|---|
| coding | 70.59 | 44.98 | 33.21 | 46.45 | 44.53 | 39.15 |
| json | 45.73 | 34.1 | 23.25 | 29.73 | 27.56 | 26.22 |
| narrative | 29.75 | 21.28 | 17.69 | 14.96 | 13.41 | 10.36 |
| prose | 33.47 | 22.84 | 20.26 | 17.98 | 15.72 | 13.77 |
| math | 71.17 | 56.47 | 44.64 | 41.28 | 43.5 | 34.74 |
| reasoning | 55.48 | 40.05 | 32.83 | 30.5 | 25.84 | 25.14 |
| summary | 31.15 | 25.15 | 21.66 | 18.5 | 18.4 | 15.52 |
| format | 48.55 | 64.68 | 53.58 | 51.69 | 46.87 | 41.28 |
| ceiling_count | 55.85 | 71.47 | 64.1 | 55.93 | 57.2 | 37.67 |

### Cold prefill (unique prefix)

| target | prompt tokens | TTFT (s) | prefill tok/s |
|---|---|---|---|
| 2000 | 2950 | 2.733 | 1079.4 |
| 8000 | 11592 | 14.287 | 811.4 |
| 32000 | 46810 | 30.711 | 1524.2 |
| 64000 | 93335 | 64.476 | 1447.6 |
