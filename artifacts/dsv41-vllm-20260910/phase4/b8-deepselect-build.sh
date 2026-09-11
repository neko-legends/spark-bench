#!/bin/bash
# B8 viability build for DeepSelect inside local/vllm-dsv41:overlay5 (no GPU needed).
# Adds sm_120/sm_121a gencode; disables the register-spill gate (sm120 prototype).
# Run ONLY when GPUs are free (build needs >10 GiB free per node).
set -u
SRC=/home/jun/dsv41-vllm/DeepSelect
IMG=local/vllm-dsv41:overlay5
cd "$SRC"
python3 - <<'PY'
p = "setup.py"
s = open(p).read()
add = ('        "-gencode", "arch=compute_120,code=sm_120",\n'
       '        "-gencode", "arch=compute_121a,code=sm_121a",\n')
if "compute_120" not in s:
    s = s.replace('        "-gencode", "arch=compute_100a,code=sm_100a",\n',
                  '        "-gencode", "arch=compute_100a,code=sm_100a",\n' + add)
    open(p, "w").write(s)
    print("patched setup.py gencode")
else:
    print("setup.py already has compute_120")
PY
docker run --rm --memory 48g -v "$SRC":/src -w /src --entrypoint bash "$IMG" -lc '
  export MAX_JOBS=2 NVCC_THREADS=2 DEEP_SELECT_DISABLE_REG_SPILL_CHECK=1 TORCH_CUDA_ARCH_LIST=12.1a
  python3 -m pip install -v . 2>&1 | tail -40
  python3 -c "import deep_select; print(\"deep_select import OK\", deep_select.__file__)"
'
