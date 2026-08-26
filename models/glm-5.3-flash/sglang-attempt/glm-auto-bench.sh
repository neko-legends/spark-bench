#!/bin/bash
# Auto-bench GLM-5.3-Flash once the tp4 server is READY.
# Results: /home/jun/glm-bench-results/  Marker: BENCH_DONE or BENCH_FAILED
RES=/home/jun/glm-bench-results
mkdir -p $RES
STATUS=/home/jun/glm-tp4-status.txt
LOG=$RES/bench-run.log
: > "$LOG"

# 1. wait for READY (max 60 min)
deadline=$(( $(date +%s) + 3600 ))
while ! grep -q '^READY' "$STATUS" 2>/dev/null; do
  grep -q '^DIED\|^WORKER_TIMEOUT' "$STATUS" 2>/dev/null && { echo "BENCH_FAILED: server died" > $RES/BENCH_FAILED; exit 1; }
  [ "$(date +%s)" -gt "$deadline" ] && { echo "BENCH_FAILED: timeout" > $RES/BENCH_FAILED; exit 1; }
  sleep 30
done
echo "[$(date -Is)] server READY, warming up" >> "$LOG"

# 2. warmup (one real completion; also verifies the new chat template works)
curl -s -m 120 http://127.0.0.1:30000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"glm-5.3-flash","messages":[{"role":"user","content":"Say exactly: warmup ok"}],"max_tokens":32}' > $RES/warmup.json 2>&1
grep -q 'warmup' $RES/warmup.json && echo "[$(date -Is)] warmup OK" >> "$LOG" || echo "[$(date -Is)] warmup RESPONSE UNUSUAL" >> "$LOG"

BENCH="docker exec glm53-tp4 python3 -m sglang.bench_serving --backend http://127.0.0.1:30000 --endpoint /v1/completions --tokenizer /models/glm --dataset-name random"

# 3. bench passes
run_bench () {
  name=$1; shift
  echo "[$(date -Is)] bench: $name" >> "$LOG"
  $BENCH "$@" --output-file /tmp/$name.json >> "$LOG" 2>&1
  docker cp glm53-tp4:/tmp/$name.json $RES/$name.json >> "$LOG" 2>&1 && echo "[$(date -Is)] saved $name" >> "$LOG"
}

# single-stream decode (interactive latency focus)
run_bench single-stream --random-input-len 2048 --random-output-len 512 --num-prompts 8 --parallel 1
# batch decode throughput
run_bench batch-16       --random-input-len 2048 --random-output-len 512 --num-prompts 48 --parallel 16
# long-context prefill
run_bench prefill-32k    --random-input-len 32768 --random-output-len 128 --num-prompts 8 --parallel 2

echo "BENCH_DONE $(date -Is)" > $RES/BENCH_DONE
echo "[$(date -Is)] ALL BENCHES DONE" >> "$LOG"
