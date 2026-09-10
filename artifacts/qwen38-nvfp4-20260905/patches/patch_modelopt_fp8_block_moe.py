#!/usr/bin/env python3
"""Teach ModelOptMixedPrecisionConfig to build FP8_BLOCK_SCALES routed experts.

In-place port (build time) of MiaAI-Lab/Qwen3.8-Flash-Next-Dual-DGX-Sparks
`files/patch_modelopt_fp8_block_moe.py` @ c2325b2 (their version operates on a
bind-mounted copy extracted from the image; ours patches the image file directly,
same anchors, same logic, guarded + idempotent like the rest of this stack).

WHY (verified against nvidia/Qwen3.8-Flash-Next-NVFP4's config.json,
2026-09-05): this checkpoint quantizes its MTP routed experts as
`mtp.layers.0.mlp.experts -> {"quant_algo": "FP8_BLOCK_SCALES", "group_size":
128}` — 128x128 block-scaled FP8. But ModelOptMixedPrecisionConfig
.get_quant_method only builds RoutedExperts for FP8 / NVFP4 / W4A16_NVFP4 /
MXFP8 and returns None for anything else, so the MTP MoE is built
*unquantized* and loading dies ~7 min in with:

    AttributeError: Layer mtp.layers.48.mlp.experts has no parameter
    'w2_weight_scale_inv' for checkpoint weight
    'mtp.layers.48.mlp.experts.0.down_proj.weight_scale_inv'

(mtp.layers.48 = num_hidden_layers + 0 — see patches/patch_checkpoint_config.py
for the layer-index alias that produces that name).

This gap is NOT image-specific: upstream vLLM has no FP8_BLOCK_SCALES branch
either — not at d4d703caf (the model-card commit, which only fixes FP8 PLE
loading, #54882) nor on main. Upgrading the image does not fix MTP here.

The fix wires the dispatch to vLLM's own Fp8MoEMethod, which sets block_quant
from weight_block_size and names its scales `weight_scale_inv` — exactly what
the checkpoint stores. The block shape is read from the checkpoint's own
group_size rather than assumed: a wrong block shape does not fail loudly, it
silently applies misaligned scales, so guessing is worse than refusing.

MiaAI measured this patch (plus the config alias) serving MTP=3 on the day-0
image at TP2+EP: 52.1 tok/s batch-1 decode vs 24.5 without MTP (2.13x), 72.8%
draft acceptance, acceptance-by-position 89% / 74.5% / 60% — the decaying
curve that proves the block shape is right.

Usage:  python3 patch_modelopt_fp8_block_moe.py <image's modelopt.py>
Anchors verified against the day-0 source at d4d0f73ef171 (peakcrosser7/vllm
release/qwen38next, "Support Qwen3.8-Flash-Next", 2026-08-26): each appears
exactly once. Refuses loudly if upstream moved; idempotent.
"""
import ast
import sys

path = sys.argv[1] if len(sys.argv) > 1 else sys.exit("usage: patch_modelopt_fp8_block_moe.py <modelopt.py>")
src = open(path).read()

if "FP8_BLOCK_SCALES" in src:
    print("patch_modelopt_fp8_block_moe: already applied, skipping")
    sys.exit(0)

HELPER = '''    def _fp8_block_scales_config(self, prefix: str):
        """Build an Fp8Config for an FP8_BLOCK_SCALES layer.

        The block shape is read from the checkpoint's own group_size rather than
        assumed: a wrong block shape does not fail loudly, it silently applies
        misaligned scales, so guessing is worse than refusing.
        """
        from vllm.model_executor.layers.quantization.fp8 import Fp8Config

        info = None
        for candidate in self._quantized_layer_prefix_candidates(prefix):
            info = self.quantized_layers.get(candidate)
            if info is None:
                prefix_dot = candidate + "."
                for key, value in self.quantized_layers.items():
                    if key.startswith(prefix_dot):
                        info = value
                        break
            if info is not None:
                break

        group_size = (info or {}).get("group_size")
        if not isinstance(group_size, int) or group_size <= 0:
            raise ValueError(
                f"FP8_BLOCK_SCALES layer {prefix} declares no usable group_size "
                f"in quantized_layers (got {group_size!r}); refusing to guess a "
                "block shape."
            )
        return Fp8Config(
            is_checkpoint_fp8_serialized=True,
            activation_scheme="dynamic",
            weight_block_size=[group_size, group_size],
        )

'''

ANCHOR_HELPER = """    @staticmethod
    def _quantized_layer_prefix_candidates(prefix: str) -> tuple[str, ...]:
"""

ANCHOR_DISPATCH = """            if quant_algo == "MXFP8":
                return ModelOptMxFp8FusedMoE(
                    quant_config=self.mxfp8_config,
                    moe_config=layer.moe_config,
                )
            return None
"""

DISPATCH = """            if quant_algo == "MXFP8":
                return ModelOptMxFp8FusedMoE(
                    quant_config=self.mxfp8_config,
                    moe_config=layer.moe_config,
                )
            if quant_algo == "FP8_BLOCK_SCALES":
                # Imported lazily: modelopt.py deliberately does not import fp8.py
                # at module scope.
                from vllm.model_executor.layers.quantization.fp8 import Fp8MoEMethod

                logger.info_once(
                    "Routed experts %s use FP8_BLOCK_SCALES; building them with "
                    "Fp8MoEMethod (block-quantized).",
                    prefix,
                )
                return Fp8MoEMethod(
                    quant_config=self._fp8_block_scales_config(prefix),
                    layer=layer,
                )
            return None
"""

for name, anchor in (("helper", ANCHOR_HELPER), ("MoE dispatch", ANCHOR_DISPATCH)):
    n = src.count(anchor)
    if n != 1:
        sys.exit(
            f"patch_modelopt_fp8_block_moe: {name} anchor count={n} (expected 1) "
            "-- day-0 image layout changed, refusing to patch blind"
        )

src = src.replace(ANCHOR_HELPER, HELPER + ANCHOR_HELPER)
src = src.replace(ANCHOR_DISPATCH, DISPATCH)

ast.parse(src)
open(path, "w").write(src)
print("patch_modelopt_fp8_block_moe: OK (FP8_BLOCK_SCALES -> Fp8MoEMethod, "
      "block size from checkpoint group_size)")
