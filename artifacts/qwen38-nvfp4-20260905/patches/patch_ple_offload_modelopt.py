#!/usr/bin/env python3
"""Let the native PLE CPU-offload path accept ModelOpt-quantized checkpoints.

Upstream's ``_get_ple_embedding_quant_method()`` only recognises ``Fp8Config``,
so with an NVFP4 (ModelOpt) checkpoint the FP8 PLE shards are rejected and
loading dies on ``ngram_embedding.weight_scale`` (first reported by @jschmied).
The PLE shards in these checkpoints are fp8 + weight_scale, exactly what the
FP8 embedding method expects, so the fix is to return that method for ModelOpt
configs too.

Applied at image build:  python3 patch_ple_offload_modelopt.py <path-to-ple_layer.py>
Guarded: refuses loudly if the function or its return class cannot be found.
"""
import re
import sys

path = sys.argv[1]
src = open(path).read()

m = re.search(
    r"def _get_ple_embedding_quant_method\([^)]*\)[^:]*:\n(\s+)\"\"\"[^\"]*\"\"\"\n",
    src,
)
if not m:
    sys.exit("patch_ple_offload_modelopt: cannot find _get_ple_embedding_quant_method")
indent = m.group(1)

r = re.search(r"return (\w+PLEFp8EmbeddingMethod)\(\)", src)
if not r:
    sys.exit("patch_ple_offload_modelopt: cannot find the FP8 embedding method return")
method_cls = r.group(1)

block = (
    f"{indent}# qwen38-quad: ModelOpt (NVFP4/FP8) checkpoints carry fp8 PLE shards\n"
    f"{indent}# + weight_scale, exactly what the FP8 method expects. Accept them\n"
    f"{indent}# so VLLM_PLE_CPU_OFFLOAD works with this checkpoint (@jschmied's fix).\n"
    f"{indent}if quant_config is not None and quant_config.__class__.__name__ in (\n"
    f"{indent}        'ModelOptNvFp4Config', 'ModelOptFp4Config', 'ModelOptFp8Config'):\n"
    f"{indent}    return {method_cls}()\n"
)
src = src[: m.end()] + block + src[m.end():]
open(path, "w").write(src)

import ast  # noqa: E402
ast.parse(src)
print(f"patch_ple_offload_modelopt: OK ({method_cls} for ModelOpt configs)")
