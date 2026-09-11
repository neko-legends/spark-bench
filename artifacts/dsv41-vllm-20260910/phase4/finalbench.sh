#!/bin/bash
# finalbench.sh — Stage C final tables on the live (champion) world. Run on forge.
set -u
BASE=http://192.168.10.1:8000/v1
MODEL=deepseek-v4.1-flash
OUT=/home/jun/dsv41-vllm/phase4/final-champion
mkdir -p "$OUT"; cd "$OUT"

for h in local anvil ember flame; do
  ( [ $h = local ] || ssh -o BatchMode=yes $h "pkill -f tel-sample2.sh >/dev/null 2>&1; nohup /tmp/tel-sample2.sh /tmp/tel-$h.csv >/dev/null 2>&1 &" ) 2>/dev/null
done
pkill -f tel-sample2.sh >/dev/null 2>&1
nohup /tmp/tel-sample2.sh /tmp/tel-local.csv >/dev/null 2>&1 &
TEL_PIDS=$!
{ echo "== final start"; free -g | head -2; } > mem.txt
ACC0=$(docker logs vllm_dsv41 2>&1 | grep -c "Mean acceptance length" || true)

# full Tony set v1 C1-C6 + prefill sweep
python3 /home/jun/dsv41-vllm/tony/bench/v41bench.py --base $BASE --model $MODEL \
  --label final-champion --out "$OUT" --levels 1,2,3,4,5,6 --prefill 2000,8000,32000,64000,100000 \
  --notes "Stage C final champion (greedy + B7 16k)" > v41bench-full.log 2>&1

# bench-decode x5
for i in 1 2 3 4 5; do
  python3 /home/jun/dsv41-vllm/bench/bench-decode.py --base-url $BASE --model $MODEL \
    --warmup 6 --n 10 > bench-decode-run$i.log 2>&1
done

# bench-depth 5k/10k + C4
python3 /home/jun/dsv41-vllm/bench/bench-depth.py --base-url $BASE --model $MODEL \
  --depths 5000,10000 --max-tokens 512 --n 3 > bench-depth.log 2>&1

# cold prefill unique-prefix probe 8k/32k/100k/400k
python3 /home/jun/dsv41-vllm/phase4/prefillprobe.py final-champion 8000,32000,100000 > prefill-probe.log 2>&1

# accept length window
ACC1=$(docker logs vllm_dsv41 2>&1 | grep -c "Mean acceptance length" || true)
docker logs vllm_dsv41 2>&1 | grep "Mean acceptance length" | tail -n +$((ACC0+1)) > accept-length-full.log
python3 - <<'PY' > accept-summary-full.json
import re, json, statistics as st
vals, rates = [], []
for line in open("accept-length-full.log"):
    m = re.search(r"Mean acceptance length: ([\d.]+)", line)
    if m: vals.append(float(m.group(1)))
    m2 = re.search(r"Avg Draft acceptance rate: ([\d.]+)%", line)
    if m2: rates.append(float(m2.group(1)))
print(json.dumps({"n": len(vals), "accept_len_mean": round(st.mean(vals),2) if vals else None,
  "accept_len_median": st.median(vals) if vals else None, "accept_rate_mean": round(st.mean(rates),1) if rates else None}))
PY

kill $TEL_PIDS 2>/dev/null
for h in local anvil ember flame; do
  ( [ $h = local ] || ssh -o BatchMode=yes $h "pkill -f tel-sample2.sh" ) 2>/dev/null
done
sleep 1
cp /tmp/tel-local.csv tel-forge.csv 2>/dev/null
for h in anvil ember flame; do scp -q $h:/tmp/tel-$h.csv tel-$h.csv 2>/dev/null; done
{ echo "== final end"; free -g | head -2; } >> mem.txt
echo "FINALBENCH DONE"
