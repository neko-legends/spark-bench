"""GB10 NoPE MLA prefill backend for GLM-5.3-Flash.

GLM-5.3-Flash uses MLA with qk_rope_head_dim=0 (NoPE) and matching
nope/v head dims (256/256). The stock FlashAttnPrefillBackend only accepts
DeepSeek geometry (rope=64). With no rope, MLA prefill is plain scaled
dot-product attention at head_size=256, which the standard FA2 varlen
kernel already supports.

This plugin overrides the FLASH_ATTN prefill backend (the only one the
selector offers on sm_121/GB10) with this NoPE-aware variant.
"""

import torch

from vllm.v1.attention.backends.fa_utils import (
    flash_attn_varlen_func,
    is_flash_attn_varlen_func_available,
)
from vllm.v1.attention.backends.mla.prefill.base import MLADimensions, MLAPrefillBackend
from vllm.v1.attention.backends.mla.prefill.registry import (
    MLAPrefillBackendEnum,
    register_mla_prefill_backend,
)


class NopeFlashAttnPrefillBackend(MLAPrefillBackend):
    @staticmethod
    def get_name() -> str:
        return "FLASH_ATTN"

    @classmethod
    def is_available(cls) -> bool:
        return is_flash_attn_varlen_func_available()

    @classmethod
    def supports_mla_dimensions(cls, mla_dimensions: MLADimensions) -> bool:
        # GLM-5.3-Flash: NoPE MLA with matching head dims.
        return mla_dimensions == MLADimensions(
            qk_nope_head_dim=256, qk_rope_head_dim=0, v_head_dim=256
        )

    def __init__(
        self,
        num_heads,
        scale,
        kv_lora_rank,
        qk_nope_head_dim,
        qk_rope_head_dim,
        v_head_dim,
        vllm_config,
    ):
        super().__init__(
            num_heads=num_heads,
            scale=scale,
            kv_lora_rank=kv_lora_rank,
            qk_nope_head_dim=qk_nope_head_dim,
            qk_rope_head_dim=qk_rope_head_dim,
            v_head_dim=v_head_dim,
            vllm_config=vllm_config,
        )

    def _varlen(
        self,
        q,
        k,
        v,
        cu_seqlens_q,
        cu_seqlens_k,
        max_seqlen_q,
        max_seqlen_k,
        causal,
        return_softmax_lse,
    ):
        kwargs = {}
        return flash_attn_varlen_func(
            q=q,
            k=k,
            v=v,
            cu_seqlens_q=cu_seqlens_q,
            cu_seqlens_k=cu_seqlens_k,
            max_seqlen_q=max_seqlen_q,
            max_seqlen_k=max_seqlen_k,
            softmax_scale=self.scale,
            causal=causal,
            return_softmax_lse=return_softmax_lse,
        )

    def run_prefill_new_tokens(
        self, q, k, v, return_softmax_lse, out=None, output_scale=None
    ):
        m = self._prefill_metadata
        return self._varlen(
            q,
            k,
            v,
            cu_seqlens_q=m.query_start_loc,
            cu_seqlens_k=m.query_start_loc,
            max_seqlen_q=m.max_query_len,
            max_seqlen_k=m.max_query_len,
            causal=True,
            return_softmax_lse=return_softmax_lse,
        )

    def run_prefill_context_chunk(self, chunk, q, k, v, out=None):
        return self._varlen(
            q,
            k,
            v,
            cu_seqlens_q=chunk.query_start_loc,
            cu_seqlens_k=chunk.cu_seq_lens,
            max_seqlen_q=chunk.max_query_len,
            max_seqlen_k=chunk.max_seq_len,
            causal=False,
            return_softmax_lse=True,
        )


register_mla_prefill_backend(
    MLAPrefillBackendEnum.FLASH_ATTN,
    "nope_mla.NopeFlashAttnPrefillBackend",
)