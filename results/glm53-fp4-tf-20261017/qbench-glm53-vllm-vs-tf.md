# qbench comparison

| area | vLLM b12x | TensorFold Zig |
|---|---|---|
| Knowledge (MMLU-200) | 88.0 % (176/200) | 88.0 % (176/200) |
| Math (GSM8K-30) | 100.0 % (30/30) | 100.0 % (30/30) |
| Coding (5 hidden tests) | 80.0 % (4/5) | 80.0 % (4/5) |
| Instruction following | 90.0 % (18/20) | 95.0 % (19/20) |
| JSON schema | 100.0 % (6/6) | 100.0 % (6/6) |
| Tool use + chains | 100.0 % (10/10) | 100.0 % (10/10) |
| Long context (passkey) | 100.0 % (3/3) | 100.0 % (3/3) |
| Summary: facts kept | 100.0 % | 100.0 % |
| Summary: stale returned (lower better) | 0.0 % | 0.0 % |
| Summary: invented numbers (lower better) | 4.2 % | 0.0 % |
| Speed: code, 1 stream | 82.0 tok/s | 58.7 tok/s |
| Speed: prose, 1 stream | 36.5 tok/s | 36.8 tok/s |
| Speed: 4 streams, aggregate | 81.2 tok/s | 61.6 tok/s |
