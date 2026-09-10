"""CPU-only source/patch checks. No vLLM/Torch imports, network, or inference."""
import ast
import difflib
import hashlib
import json
import os
import math
import random
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest

ROOT = Path(__file__).resolve().parent
I = ROOT / 'installed'
TICKET = ROOT / 'upstream/reederey-ticket/overlay'
QUANT = I / 'exllamav3/exllamav3_ext/quant'
FILES = ('exl3_devctx.cu', 'exl3_devctx.cuh', 'exl3_moe.cu', 'exl3_moe.cuh', 'exl3_moe_common.cuh', 'exl3_moe_kernel.cuh')

def function_ns(path, names, **globals_):
    tree = ast.parse(path.read_text())
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    assert len(nodes) == len(names)
    ns = dict(globals_)
    code = 'from __future__ import annotations\n' + '\n'.join(ast.unparse(n) for n in nodes)
    exec(compile(code, str(path), 'exec'), ns)
    return ns

class SourceChecks(unittest.TestCase):
    def test_launcher_identity_and_missing_forwarding(self):
        launcher = ROOT/'host/home/jun/launch-glm53-exl3-tp4.sh'
        self.assertEqual(launcher.read_bytes(), (ROOT/'launcher.snapshot.sh').read_bytes())
        text = launcher.read_text()
        self.assertIn('LONG_PREFILL_TOKEN_THRESHOLD=1792', text)
        self.assertNotIn('-e LONG_PREFILL_TOKEN_THRESHOLD', text)
        actual = (ROOT/'actual-serve-argv.json').read_text()
        self.assertIn('long_prefill_flag_present False', actual)

    def test_baked_patch_sweep_confounds(self):
        build=(ROOT/'upstream/image-build.txt').read_text()
        for p in ('patch_glm5_drafter_group.py','patch_scheduler_decode_floor.py'):
            self.assertIn('RUN python3 /opt/glm53/'+p, build)
        self.assertIn('RUN python3 /opt/glm53/patch_spinwait.py --preflight',build)
        self.assertIn('DFLASH2-DRAFTER-GROUP', (I/'vllm/v1/core/kv_cache_utils.py').read_text())
        self.assertIn('busy_loop_s: float = 0.016', (I/'vllm/distributed/device_communicators/shm_broadcast.py').read_text())

    def test_decode_floor_cannot_reduce_pure_decode_tokens(self):
        ns=function_ns(I/'vllm/v1/core/sched/scheduler.py',{'_glm53_mixed_prefill_policy'},os=os)
        policy=ns['_glm53_mixed_prefill_policy']
        old=dict(os.environ)
        try:
            os.environ.update(GLM53_MIXED_PREFILL_CHUNK='skip',GLM53_MIXED_PREFILL_SMALL_OK='2048')
            rows=[NS(request_id=str(i),num_computed_tokens=400,num_prompt_tokens=64) for i in range(4)]
            for r in rows:
                cap=policy(rows,r)
                self.assertEqual(cap,0)
                # Exact guard from installed scheduler: helper value unused for decoders.
                self.assertFalse(cap is not None and r.num_computed_tokens < r.num_prompt_tokens)
            small=NS(request_id='s',num_computed_tokens=0,num_prompt_tokens=100)
            large=NS(request_id='l',num_computed_tokens=0,num_prompt_tokens=100000)
            self.assertIsNone(policy(rows,small)); self.assertEqual(policy(rows,large),0)
        finally:
            os.environ.clear();os.environ.update(old)

    def test_decode_dispatch_bounds(self):
        text=(I/'vllm/model_executor/layers/quantization/exl3.py').read_text()
        tree=ast.parse(text)
        fun=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='apply_exl3_fused_moe')
        guard=next(n for n in fun.body if isinstance(n,ast.If) and ast.unparse(n.test)=='tokens <= cap')
        self.assertIsInstance(guard.body[-1],ast.Return)
        self.assertNotIn('synchronize',ast.unparse(guard))
        self.assertNotIn('.item()',ast.unparse(guard))
        self.assertIn('max_num_seqs * decode_query_len * 2', (I/'vllm/config/vllm.py').read_text())
        fi=(I/'flashinfer/mla/_sparse_mla_sm120.py').read_text()
        self.assertIn('_DECODE_MAX_TOKENS = 64',fi)
        for c in range(1,5):
            n=c*8
            self.assertLessEqual(n,64)
            self.assertLessEqual(n,128)
        self.assertEqual(min(4*8*2,512,7168),64)

    def test_draft_loading_retains_target_parallel_config(self):
        p=I/'vllm/v1/worker/gpu/spec_decode/dflash/utils.py'
        tree=ast.parse(p.read_text())
        f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='load_dflash_model')
        self.assertNotIn('draft_parallel_config',ast.unparse(f))
        for n in ast.walk(f):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='replace':
                self.assertNotIn('parallel_config',[k.arg for k in n.keywords])
        q=(I/'vllm/model_executor/models/qwen3_dflash.py').read_text()
        self.assertIn('tp_size = get_tensor_model_parallel_world_size()',q)

    def test_exact_ticket_backport_matches_installed_pin(self):
        for name in FILES:
            self.assertEqual((QUANT/name).read_bytes(),(TICKET/'exl3-ticket/pristine'/name).read_bytes(),name)
        self.assertNotIn('MOE_SCHED_INTS',(QUANT/'exl3_devctx.cuh').read_text())
        self.assertIn('expert_idx_assign++ % concurrency', (QUANT/'exl3_moe_kernel.cuh').read_text())

    def test_ticket_installer_idempotence_drift_and_optout(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix='cpu-check-') as d:
            p=Path(d);q=p/'quant';q.mkdir()
            for name in FILES: shutil.copyfile(QUANT/name,q/name)
            cmd=[sys.executable,'-B',str(TICKET/'patch_exl3_ticket_scheduler.py'),str(p)]
            env=dict(os.environ,GLM53_EXL3_TICKET_SCHEDULER='0')
            a=subprocess.run(cmd,env=env,capture_output=True,text=True)
            self.assertEqual(a.returncode,0,a.stderr)
            self.assertEqual((q/FILES[0]).read_bytes(),(QUANT/FILES[0]).read_bytes())
            env['GLM53_EXL3_TICKET_SCHEDULER']='1'
            for _ in range(2):
                a=subprocess.run(cmd,env=env,capture_output=True,text=True)
                self.assertEqual(a.returncode,0,a.stderr)
                for name in FILES:self.assertEqual((q/name).read_bytes(),(TICKET/'exl3-ticket/patched'/name).read_bytes())
            # Mixed state refuses before any writes.
            shutil.copyfile(QUANT/FILES[0],q/FILES[0])
            before={n:(q/n).read_bytes() for n in FILES}
            a=subprocess.run(cmd,env=env,capture_output=True,text=True)
            self.assertNotEqual(a.returncode,0)
            self.assertEqual(before,{n:(q/n).read_bytes() for n in FILES})
            # Unknown bytes refuse before any writes.
            (q/FILES[0]).write_bytes(b'// drift\n'+before[FILES[0]])
            before={n:(q/n).read_bytes() for n in FILES}
            a=subprocess.run(cmd,env=env,capture_output=True,text=True)
            self.assertNotEqual(a.returncode,0)
            self.assertEqual(before,{n:(q/n).read_bytes() for n in FILES})

    def test_topk_candidate_syntax_and_math_not_gpu(self):
        # Reference proof only: no Torch is installed locally. This does NOT
        # validate tensor kernels, BF16 rounding, tie IDs, or CUDA capture.
        src=(ROOT/'candidate-topk/vllm/model_executor/layers/logits_processor.py').read_text()
        ast.parse(src)
        fn=next(n for c in ast.parse(src).body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='get_top_k_tokens_glm53')
        body=ast.unparse(fn)
        self.assertLess(body.index('torch.tanh'),body.index('logits *= self.scale'))
        self.assertLess(body.index('logits *= self.scale'),body.index('torch.topk'))
        self.assertNotIn('.float()',body)
        rng=random.Random(917)
        for shards in (1,4):
            for k in (1,16):
                for _ in range(20):
                    vals=[rng.uniform(-2,2) for _ in range(128*shards)]
                    for cap,scale in ((None,1),(10,1.7),(None,-2)):
                        transform=lambda x: (math.tanh(x/cap)*cap if cap else x)*scale
                        pairs=[(transform(v),i) for i,v in enumerate(vals)]
                        dense=sorted(pairs,reverse=True)[:k]
                        local=[]
                        for s in range(shards):local.extend(sorted(pairs[s*128:(s+1)*128],reverse=True)[:k])
                        self.assertEqual(dense,sorted(local,reverse=True)[:k])

    def test_existing_python_adapter_accepts_29_and_30_args(self):
        ns=function_ns(I/'vllm/model_executor/layers/quantization/exl3.py',{'_exl3_moe_accepts_num_active','_exl3_moe_launch'},MOE_ACT_SILU=0)
        class Fn:
            def __init__(self,n): self.__doc__='exl3_moe('+','.join(f'arg{i}: Any' for i in range(n))+')';self.args=None
            def __call__(self,*args):self.args=args
        keys=('gate_trellis','gate_suh','gate_svh','up_trellis','up_suh','up_svh','down_trellis','down_suh','down_svh')
        for n in (29,30):
            fn=Fn(n)
            compatible=ns['_exl3_moe_accepts_num_active'](fn)
            self.assertEqual(compatible,n==30)
            ns['_exl3_moe_launch'](fn,None,None,None,None,None,(None,)*4,dict.fromkeys(keys),4,10,-1 if compatible else None)
            self.assertEqual(len(fn.args),n)
            if n==30:self.assertEqual(fn.args[-1],-1)

if __name__=='__main__':
    unittest.main(verbosity=2)
