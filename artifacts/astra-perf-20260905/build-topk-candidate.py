"""Construct an unapplied, artifact-only candidate; preserve installed logit semantics."""
import ast
import difflib
from pathlib import Path
R=Path(__file__).resolve().parent
files={}
p='vllm/model_executor/layers/logits_processor.py'
s=(R/'installed'/p).read_text()
helper='''    def get_top_k_tokens_glm53(
        self,
        lm_head: VocabParallelEmbedding,
        hidden_states: torch.Tensor,
        k: int,
        embedding_bias: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Trial-only DFlash2 top-k reduction; no full-vocabulary collective.

        Based on upstream 32601ef7 get_top_k_tokens, but intentionally keep
        THIS image's cap-then-scale order and dtype, applying transforms before
        selection. Do not import upstream's reversed order / fp32 conversion.
        Equal-score candidate ties need explicit GPU acceptance testing.
        """
        logits = self._apply_head(lm_head, hidden_states, embedding_bias)
        if self.soft_cap is not None:
            logits = logits / self.soft_cap
            logits = torch.tanh(logits)
            logits = logits * self.soft_cap
        if self.scale != 1.0:
            logits *= self.scale
        num_pad = lm_head.shard_indices.num_org_vocab_padding
        if num_pad > 0:
            logits[..., -num_pad:] = -float("inf")
        values, ids = torch.topk(logits, k, dim=-1)
        ids = ids.to(torch.int64) + lm_head.shard_indices.org_vocab_start_index
        if lm_head.tp_size > 1:
            values = tensor_model_parallel_all_gather(values, dim=-1)
            ids = tensor_model_parallel_all_gather(ids, dim=-1)
            values, selected = torch.topk(values, k, dim=-1)
            ids = ids.gather(-1, selected)
        return ids, values

'''
anchor='    def extra_repr(self) -> str:\n'
assert s.count(anchor)==1
files[p]=s.replace(anchor,helper+anchor)
p='vllm/model_executor/models/qwen3_dflash2.py'
s=(R/'installed'/p).read_text()
old='''        logits = self.candidate_logits_processor(self.lm_head, hidden_states)
        assert logits is not None
        top_k = self.model.candidate_selector.top_k
        unary_logits, candidate_ids = torch.topk(logits, top_k, dim=-1)
        return candidate_ids, unary_logits
'''
new='''        # Experimental image only. No change to target sampling/rejection or
        # draft probabilities; only reduce candidate collection across TP.
        # Scope: current unmodified vocabulary, no LoRA/added-vocabulary lane.
        return self.candidate_logits_processor.get_top_k_tokens_glm53(
            self.lm_head, hidden_states, self.model.candidate_selector.top_k
        )
'''
assert s.count(old)==1
files[p]=s.replace(old,new)
diff=''
for path,source in files.items():
    ast.parse(source,filename=path)
    original=(R/'installed'/path).read_text()
    out=R/'candidate-topk'/path
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(source)
    diff+=''.join(difflib.unified_diff(original.splitlines(True),source.splitlines(True),fromfile='a/'+path,tofile='b/'+path))
(R/'candidate-dflash-distributed-topk.diff').write_text(diff)
print('Wrote candidate-dflash-distributed-topk.diff; syntax OK; NOT applied to installed or serving files')
