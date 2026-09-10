#!/bin/bash
# shortbench.sh <label> [reps=3] — phase-4 arm short bench on forge.
# Per rep: v41bench C1+C4 (9 categories) + cold prefill 8k/32k.
# Once:    bench-decode (warmup4,n8 distribution), prefill 100k, accept-length window,
#          telemetry CSVs (clocks/power, all 4 nodes), free/swap snapshot.
set -u
LABEL=$1
REPS=${2:-3}
BASE=http://192.168.10.1:8000/v1
MODEL=deepseek-v4.1-flash
OUT=/home/jun/dsv41-vllm/phase4/$LABEL
mkdir -p "$OUT"
cd "$OUT"

# telemetry on all 4 nodes
for h in local anvil ember flame; do
  ( [ $h = local ] || ssh -o BatchMode=yes $h "pkill -f tel-sample2.sh >/dev/null 2>&1; nohup /tmp/tel-sample2.sh /tmp/tel-$h.csv >/dev/null 2>&1 &" ) 2>/dev/null
done
pkill -f tel-sample2.sh >/dev/null 2>&1
nohup /tmp/tel-sample2.sh /tmp/tel-local.csv >/dev/null 2>&1 &
TEL_PIDS=$!

free_snapshot() {
  { echo "== $1"; free -g | head -2; grep -E "SwapTotal|SwapFree" /proc/meminfo; }
  for h in anvil ember flame; do ssh -o BatchMode=yes $h "echo \"== $h\"; free -g | head -2; grep -E 'SwapTotal|SwapFree' /proc/meminfo" 2>/dev/null; done
}
free_snapshot "$LABEL start" > mem.txt 2>&1

# accept-length baseline marker (head log line count)
ACC0=$(docker logs vllm_dsv41 2>&1 | grep -c "Mean acceptance length" || true)

# reps (no prefill sweep inside v41bench — prefix cache pollutes repeats)
for r in $(seq 1 "$REPS"); do
  python3 /home/jun/dsv41-vllm/tony/bench/v41bench.py --base $BASE --model $MODEL \
    --label "${LABEL}-rep${r}" --out "$OUT" --levels 1,4 --prefill "" \
    --notes "phase4 arm $LABEL rep $r" > "v41bench-rep${r}.log" 2>&1
  echo "rep $r done: $(grep -c 'agg' v41bench-rep${r}.log) rows"
done

# cold prefill probes (unique prefix per run)
mkdir -p /home/jun/dsv41-vllm/phase4/$LABEL
python3 /home/jun/dsv41-vllm/phase4/prefillprobe.py "$LABEL" 8000,32000,100000 > prefill-probe.log 2>&1

# bench-decode distribution (bimodality)
python3 /home/jun/dsv41-vllm/bench/bench-decode.py --base-url $BASE --model $MODEL \
  --warmup 4 --n 8 > bench-decode.log 2>&1

# 100k+400k cold prefill probes handled by prefillprobe.py above

# TTFT@2k
python3 /home/jun/dsv41-vllm/tony/bench/v41bench.py --base $BASE --model $MODEL \
  --label "${LABEL}-ttft2k" --out "$OUT" --levels 1 --prefill 2000 --notes "ttft2k" > v41bench-ttft2k.log 2>&1

# accept-length window
ACC1=$(docker logs vllm_dsv41 2>&1 | grep -c "Mean acceptance length" || true)
docker logs vllm_dsv41 2>&1 | grep "Mean acceptance length" | tail -n +$((ACC0+1)) | head -n $((ACC1-ACC0)) > accept-length.log
python3 - << 'EOF' > accept-summary.json
import re
vals, rates = [], []
for line in open("accept-length.log"):
    m = re.search(r"Mean acceptance length: ([\d.]+)", line)
    if m: vals.append(float(m.group(1)))
    m2 = re.search(r"Avg Draft acceptance rate: ([\d.]+)%", line)
    if m2: rates.append(float(m2.group(1)))
import json, statistics as st
print(json.dumps({"n": len(vals),
  "accept_len_mean": round(st.mean(vals),2) if vals else None,
  "accept_len_median": st.median(vals) if vals else None,
  "accept_rate_mean": round(st.mean(rates),1) if rates else None}))
EOF

# stop telemetry, collect
kill $TEL_PIDS 2>/dev/null
for h in local anvil ember flame; do
  ( [ $h = local ] || ssh -o BatchMode=yes $h "pkill -f tel-sample2.sh" ) 2>/dev/null
done
sleep 1
cp /tmp/tel-local.csv "tel-forge.csv" 2>/dev/null
for h in anvil ember flame; do scp -q $h:/tmp/tel-$h.csv "tel-$h.csv" 2>/dev/null; done

free_snapshot "$LABEL end" >> mem.txt 2>&1
echo "SHORTBENCH DONE $LABEL"
