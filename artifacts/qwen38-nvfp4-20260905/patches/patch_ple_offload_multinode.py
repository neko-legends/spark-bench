#!/usr/bin/env python3
"""Allow VLLM_PLE_CPU_OFFLOAD on multi-node deployments.

Upstream's ``_validate_ple_offload_config`` blanket-rejects ``nnodes != 1``,
but the offload process is spawned per WorkerProc (``spawn_ple_offload()`` in
``multiproc_executor``), every rank gets its own node-local table process,
and the pidfd tensor handover never crosses a host boundary. The check is
conservatism, not architecture. This patch downgrades it to a warning.

Applied at image build:  python3 patch_ple_offload_multinode.py <gpu_worker.py>
Guarded: refuses loudly if the exact check is not found.
"""
import ast
import sys

path = sys.argv[1]
src = open(path).read()

old = '''        if parallel_config.nnodes != 1:
            unsupported.append(f"nnodes={parallel_config.nnodes}")'''
new = '''        if parallel_config.nnodes != 1:
            # qwen38-quad: the offload process is spawned per WorkerProc and is
            # node-local (pidfd handover never crosses hosts), multi-node works.
            logger.warning(
                "VLLM_PLE_CPU_OFFLOAD with nnodes=%d: per-node offload "
                "processes, enabled by the qwen38-quad patch.",
                parallel_config.nnodes,
            )'''

if old not in src:
    sys.exit("patch_ple_offload_multinode: nnodes check not found, layout changed?")
src = src.replace(old, new)
open(path, "w").write(src)
ast.parse(src)
print("patch_ple_offload_multinode: OK (nnodes check downgraded to warning)")
