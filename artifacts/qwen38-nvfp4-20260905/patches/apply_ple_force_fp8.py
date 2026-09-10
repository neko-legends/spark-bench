#!/usr/bin/env python3
"""Apply the getrefined PLE FP8 resolver (ple-force-fp8.patch) to the day-0 image.

This is a faithful, guarded port of the 3-line patch from
getrefined/Qwen3.8-Flash-Next-NVFP4-vLLM-DGX-Spark (commit f736930):

    +    import os
    +    if os.environ.get("PLE_FORCE_FP8") == "1":
    +        return Qwen3_8FlashNextPLEFp8EmbeddingMethod()

inserted at the TOP of ``_get_ple_embedding_quant_method()`` in
``vllm/models/qwen3_8_flash_next/nvidia/ple_layer.py`` — i.e. ABOVE the
``isinstance(quant_config, Fp8Config)`` gate, because that gate is the first
thing that rejects ModelOpt-NVFP4 / mixed-precision parent configs.

This is the pre-rename (day-0 image) equivalent of upstream vLLM fix
d4d703caf (#54882, "[Bugfix][Model] Fix FP8 PLE loading in mixed ModelOpt
checkpoints", 2026-09-03), which is NOT in the pinned day-0 image (tag pushed
2026-08-26). The nvidia/Qwen3.8-Flash-Next-NVFP4 checkpoint stores the PLE
table as F8_E4M3 shards + one global BF16 weight_scale inside
model-fp8-mtp-ple.safetensors, declared under a ModelOpt MIXED_PRECISION
quant config — exactly the layout this resolver lets through.

Applied at image build:  python3 apply_ple_force_fp8.py <path-to-ple_layer.py>
Refuses loudly if the function or the gate cannot be found.
"""
import ast
import sys

path = sys.argv[1]
src = open(path).read()

FUNC = "def _get_ple_embedding_quant_method("
GATE = "    if not isinstance(quant_config, Fp8Config):\n"
RET = "Qwen3_8FlashNextPLEFp8EmbeddingMethod"

if FUNC not in src:
    sys.exit("apply_ple_force_fp8: cannot find _get_ple_embedding_quant_method")
if GATE not in src:
    sys.exit("apply_ple_force_fp8: Fp8Config gate not found, layout changed?")
if RET not in src:
    sys.exit(f"apply_ple_force_fp8: {RET} not found in ple_layer.py")
if "PLE_FORCE_FP8" in src:
    print("apply_ple_force_fp8: already applied, skipping")
    sys.exit(0)

# Insert immediately ABOVE the Fp8Config gate (getrefined's placement rule:
# an env-gated early return must go above the first gate).
block = (
    "    # qwen38-gb10: PLE_FORCE_FP8 (getrefined ple-force-fp8.patch, pre-rename\n"
    "    # backport of vllm#54882): the nvidia NVFP4 checkpoint carries fp8 PLE\n"
    "    # shards + a global weight_scale under a ModelOpt config; the stock\n"
    "    # Fp8Config gate below rejects it. Env-gated, default off.\n"
    "    import os\n"
    '    if os.environ.get("PLE_FORCE_FP8") == "1":\n'
    f"        return {RET}()\n"
)

idx = src.index(GATE)
src = src[:idx] + block + src[idx:]
open(path, "w").write(src)
ast.parse(src)
print(f"apply_ple_force_fp8: OK ({RET} above the Fp8Config gate, env-gated)")
