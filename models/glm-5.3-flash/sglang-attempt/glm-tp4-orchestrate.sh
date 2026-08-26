#!/bin/bash
# GLM TP4 orchestrator: wait for workers, relaunch rank0, record verdict.
# Runs detached on forge. Status file: /home/jun/glm-tp4-status.txt
STATUS=/home/jun/glm-tp4-status.txt
LOG=/home/jun/glm-tp4-orchestrate.log
echo "WAITING_FOR_WORKERS $(date -Is)" > "$STATUS"
: > "$LOG"

# 1. wait until all 3 workers report glm53-tp4 running (max 30 min)
deadline=$(( $(date +%s) + 1800 ))
while true; do
  up=0
  for h in anvil ember flame; do
    st=$(ssh -o BatchMode=yes -o ConnectTimeout=5 $h "docker ps --filter name=glm53-tp4 --format '{{.Names}}'" 2>/dev/null)
    [ -n "$st" ] && up=$((up+1))
  done
  echo "[$(date -Is)] workers up: $up/3" >> "$LOG"
  [ "$up" = "3" ] && break
  if [ "$(date +%s)" -gt "$deadline" ]; then
    echo "WORKER_TIMEOUT $(date -Is) up=$up" > "$STATUS"; exit 1
  fi
  sleep 30
done

# 2. (re)launch rank 0 on forge
echo "[$(date -Is)] all workers up, launching rank0" >> "$LOG"
bash /home/jun/glm-tp4-run.sh 0 >> "$LOG" 2>&1
echo "RANK0_LAUNCHING $(date -Is)" > "$STATUS"

# 3. watch for readiness or death (max 45 min — 306GB weight load is slow)
deadline=$(( $(date +%s) + 2700 ))
while true; do
  if docker logs glm53-tp4 2>&1 | grep -q "The server is fired up and ready to roll"; then
    echo "READY $(date -Is)" > "$STATUS"; exit 0
  fi
  if ! docker ps --filter name=glm53-tp4 --format x | grep -q x; then
    echo "DIED $(date -Is) — last logs:" > "$STATUS"
    docker logs glm53-tp4 2>&1 | tail -20 >> "$STATUS"
    exit 1
  fi
  sleep 20
done
