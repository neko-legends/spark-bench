# qbench comparison

| area | dsv41-zig-rebench-after-fabric-fix-20261015 | glm53-fp4-vllm-20261017 |
|---|---|---|
| Knowledge (MMLU-200) | 88.5 % (177/200) | 88.0 % (176/200) |
| Math (GSM8K-30) | 100.0 % (30/30) | 100.0 % (30/30) |
| Coding (5 hidden tests) | 80.0 % (4/5) | 80.0 % (4/5) |
| Instruction following | 90.0 % (18/20) | 90.0 % (18/20) |
| JSON schema | 100.0 % (6/6) | 100.0 % (6/6) |
| Tool use + chains | 100.0 % (10/10) | 100.0 % (10/10) |
| Long context (passkey) | 100.0 % (3/3) | 100.0 % (3/3) |
| Summary: facts kept | 100.0 % | 100.0 % |
| Summary: stale returned (lower better) | 0.0 % | 0.0 % |
| Summary: invented numbers (lower better) | 0.0 % | 4.2 % |
| Speed: code, 1 stream | 155.3 tok/s | 82.0 tok/s |
| Speed: prose, 1 stream | 72.0 tok/s | 36.5 tok/s |
| Speed: 4 streams, aggregate | 172.1 tok/s | 81.2 tok/s |
