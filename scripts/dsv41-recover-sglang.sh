#!/usr/bin/env bash
# spark-forge-recover-sglang.sh — recovery entry for the SGLang DSV4.1 world
# (2026-09-14 cutover). Same doctrine as the vLLM wrapper: an API that answers
# /health and /v1/models is NOT proof of life — the 2026-09-13 wedge kept
# answering both while the engine produced nothing. So the fast path requires a
# real 1-token completion; only then is there nothing to do.
set -uo pipefail
KIT=/home/jun/dsv41-sglang-trial-20260914/mia
API=http://127.0.0.1:8000
MODEL=deepseek-v4.1-flash
PROBE_TIMEOUT="${RECOVER_PROBE_TIMEOUT:-300}"

ssh_q(){ ssh -o BatchMode=yes -o ConnectTimeout=15 forge "$@"; }

# busy? = SGLang's own load endpoint says requests are running or queued. A world
# mid-prefill of a 200k-token prompt will NOT answer a 1-token probe inside any
# short budget — and on 2026-09-14 an earlier version of this script read exactly
# that as "wedged" and killed a healthy, busy world. Never again: check load first.
world_load(){  # prints "running waiting" or empty on failure
  ssh_q "curl -fsS --max-time 8 $API/v1/loads" 2>/dev/null | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: sys.exit(0)
r=w=0
for e in (d.get('loads') or []):
    r+=int(e.get('num_running_reqs') or 0); w+=int(e.get('num_waiting_reqs') or 0)
print(r,w)" 2>/dev/null
}

probe_ok(){ ssh_q "curl -fsS --max-time $PROBE_TIMEOUT -H 'Content-Type: application/json' -X POST $API/v1/chat/completions -d '{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":1}' >/dev/null" 2>/dev/null; }

# fast path: model listed AND a 1-token completion answers
if ssh_q "curl -fsS --max-time 5 $API/v1/models | grep -q $MODEL"; then
  if probe_ok; then
    echo "[recover-sglang] API serving $MODEL and a 1-token completion answered — nothing to do."
    exit 0
  fi
  load="$(world_load)"
  running="${load%% *}"; waiting="${load##* }"
  if [ -n "$load" ] && [ "${running:-0}" -gt 0 -o "${waiting:-0}" -gt 0 ] 2>/dev/null; then
    echo "[recover-sglang] no completion within ${PROBE_TIMEOUT}s, but the world reports running=$running waiting=$waiting — BUSY, not wedged. Waiting instead of restarting."
    for i in $(seq 1 6); do
      sleep 60
      if probe_ok; then
        echo "[recover-sglang] completion answered after busy wait — nothing to do."
        exit 0
      fi
      load="$(world_load)"; running="${load%% *}"; waiting="${load##* }"
      echo "[recover-sglang] still busy (running=$running waiting=$waiting) after ${i}m"
      if [ -n "$load" ] && [ "${running:-0}" = 0 ] && [ "${waiting:-0}" = 0 ]; then
        # went idle yet still cannot answer a 1-token request: that IS a wedge
        if ! probe_ok; then
          echo "[recover-sglang] idle but still not answering — engine wedged; restarting the world."
          break
        fi
        echo "[recover-sglang] completion answered — nothing to do."; exit 0
      fi
    done
    if [ "$i" = 6 ] && probe_ok; then
      echo "[recover-sglang] completion answered after long busy wait — nothing to do."; exit 0
    fi
  else
    echo "[recover-sglang] API lists $MODEL, no load reported, and no completion within ${PROBE_TIMEOUT}s — engine wedged; restarting the world."
  fi
fi

# boot-in-progress guard: a container younger than 15 min means someone is already booting
age=$(ssh_q "docker inspect -f '{{.State.StartedAt}}' dsv41-head 2>/dev/null" || true)
if [ -n "$age" ]; then
  started=$(date -d "$age" +%s 2>/dev/null || echo 0)
  now=$(date +%s)
  if [ "$started" -gt 0 ] && [ $((now - started)) -lt 900 ]; then
    echo "[recover-sglang] dsv41-head is $((now - started))s old and not serving yet — a boot is in progress; leaving it alone."
    exit 0
  fi
fi

echo "[recover-sglang] stopping the world (head first), then serving again..."
ssh_q "cd $KIT && ./start-tp4.sh stop" || true
# let unified memory return before relaunch (phantom CUDA OOM otherwise)
for i in $(seq 1 24); do
  apps=$(ssh_q "nvidia-smi --query-compute-apps=pid --format=csv,noheader | wc -l" 2>/dev/null || echo 1)
  [ "${apps:-1}" = "0" ] && break
  sleep 5
done
ssh_q "cd $KIT && ./start-tp4.sh serve"
for i in $(seq 1 90); do
  if ssh_q "curl -fsS --max-time 5 -H 'Content-Type: application/json' -X POST $API/v1/chat/completions -d '{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":1}' >/dev/null" 2>/dev/null; then
    echo "[recover-sglang] RECOVERED: SGLang world is serving $MODEL on $API"
    # prewarm so the first real turn does not pay the Triton JIT cost (2026-09-14: cold first inference took 102s)
    ssh_q "timeout 900 python3 /home/jun/dsv41-vllm/ops/prewarm.py http://127.0.0.1:8000/v1 $MODEL" 2>&1 | sed 's/^/[recover-sglang] /' || true
    exit 0
  fi
  sleep 10
done
echo "[recover-sglang] FAIL: world did not come back after stop+serve"
exit 1
