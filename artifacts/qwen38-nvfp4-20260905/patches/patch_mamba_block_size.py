#!/usr/bin/env python3
"""Fix prefix caching (mamba cache mode 'align') for hybrid models whose KV groups include a small-block
spec (Qwen3.8-Flash-Next QSA raw-key ring, block 8/16): EngineCore overwrites cache_config.block_size with
the MIN group block size (v1/engine/core.py), but the align-mode state-slot seed (worker) and the
block-aligned prefill split (scheduler) used it as the *mamba* block size (1600). Consequences: a prefix
hit seeds the state slot at (num_computed-1)//16 -> out-of-row column -> null block -> all-zero restored
state; chunk boundaries never land on mamba boundaries so states are almost never cached.
Diagnosed 2026-08-29 on GB10 with state checksums; see docs/recette-flash-next-vllm.md."""
import sys
SP = sys.argv[1]
MH = f"{SP}/vllm/v1/worker/gpu/model_states/mamba_hybrid.py"
SC = f"{SP}/vllm/v1/core/sched/scheduler.py"
s = open(MH).read()
a = "                (new_req_data.num_computed_tokens - 1) // self.cache_config.block_size\n"
assert s.count(a) == 1, "mamba_hybrid seed line not found"
s = s.replace(a, "                (new_req_data.num_computed_tokens - 1)\n"
                 "                // (self.cache_config.mamba_block_size or self.cache_config.block_size)\n")
open(MH, "w").write(s)
t = open(SC).read()
b = "        block_size = self.cache_config.block_size\n        # The last block-aligned position whose state can be cached."
assert t.count(b) == 1, "scheduler split line not found"
t = t.replace(b, "        block_size = self.block_size  # scheduler block size (LCM of groups) == mamba block size\n"
                 "        # The last block-aligned position whose state can be cached.")
open(SC, "w").write(t)
import ast; ast.parse(s); ast.parse(t); print("mamba block_size fix applied OK")
