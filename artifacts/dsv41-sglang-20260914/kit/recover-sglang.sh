#!/usr/bin/env bash
# recover-sglang.sh — forge-local recovery for the SGLang DSV4.1 world (2026-09-14 cutover).
# Runs ON forge (no ssh), used by dsv41-sglang-world.service at boot and by the watchdog
# wrapper. Doctrine, both lessons learned the hard way:
#   * API-up is not liveness — require a real 1-token completion (2026-09-13 wedge: the
#     HTTP front end answered /health and /v1/models while the engine produced nothing).
#   * BUSY is not wedged — a world mid-prefill of a 200k-token prompt will not answer a
#     1-token probe inside any short budget. /v1/loads tells us which we are looking at
#     (2026-09-14: an earlier wrapper killed a healthy, busy world because of this).
set -uo pipefail
KIT=/home/jun/dsv41-sglang-trial-20260914/mia
LOG=/home/jun/dsv41-sglang-trial-20260914/recover.log
API=http://127.0.0.1:8000
MODEL=deepseek-v4.1-flash
PROBE_TIMEOUT="${RECOVER_PROBE_TIMEOUT:-300}"
say(){ echo "[$(date -Is)] $*" | tee -a "$LOG"; }

probe_ok(){
  curl -fsS --max-time "$PROBE_TIMEOUT" -H 'Content-Type: application/json' \
    -X POST "$API/v1/chat/completions" \
    -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":1}" \
    >/dev/null 2>&1
}

load_state(){ # prints "running waiting" or nothing
  curl -fsS --max-time 8 "$API/v1/loads" 2>/dev/null | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: sys.exit(0)
r=w=0
for e in (d.get('loads') or []):
    r+=int(e.get('num_running_reqs') or 0); w+=int(e.get('num_waiting_reqs') or 0)
print(r,w)" 2>/dev/null
}

mkdir -p "$(dirname "$LOG")"
say "recover-sglang start"

if curl -fsS --max-time 5 "$API/v1/models" 2>/dev/null | grep -q "$MODEL"; then
  if probe_ok; then
    say "serving and answering a completion — nothing to do."
    exit 0
  fi
  read -r running waiting <<<"$(load_state)"
  if [ "${running:-0}" -gt 0 ] || [ "${waiting:-0}" -gt 0 ]; then
    say "no completion in ${PROBE_TIMEOUT}s but world is BUSY (running=$running waiting=$waiting) — waiting up to 6 min instead of restarting."
    for i in $(seq 1 6); do
      sleep 60
      if probe_ok; then say "completion answered after busy wait — nothing to do."; exit 0; fi
      read -r running waiting <<<"$(load_state)"
      say "still busy (running=$running waiting=$waiting) after ${i}m"
      if [ "${running:-1}" = 0 ] && [ "${waiting:-1}" = 0 ]; then say "went idle and still not answering — wedged."; break; fi
    done
    probe_ok && { say "completion answered — nothing to do."; exit 0; }
  else
    say "model listed, no load reported, no completion in ${PROBE_TIMEOUT}s — wedged."
  fi
fi

# boot-in-progress guard
if docker inspect -f '{{.State.StartedAt}}' dsv41-head >/dev/null 2>&1; then
  started=$(date -d "$(docker inspect -f '{{.State.StartedAt}}' dsv41-head 2>/dev/null)" +%s 2>/dev/null || echo 0)
  age=$(( $(date +%s) - ${started:-0} ))
  if [ "${started:-0}" -gt 0 ] && [ "$age" -lt 900 ]; then
    say "dsv41-head is ${age}s old and not serving yet — a boot is in progress; leaving it alone."
    exit 0
  fi
fi

say "restarting the SGLang world (stop, memory drain, share, serve)..."
cd "$KIT" || exit 1
./start-tp4.sh stop >>"$LOG" 2>&1 || true
for i in $(seq 1 24); do
  apps=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | wc -l)
  [ "${apps:-1}" = "0" ] && break
  sleep 5
done
# share BEFORE serve (2026-09-14 lesson): the workers read the checkpoint from a docker
# volume backed by this node's NFSv4 export. If the exporter is gone, `serve`'s readiness
# probe blocks forever inside `docker run -v dsv41-weights:/m`, and the boot looks hung.
# 2026-09-16: the uncensored profile mounts the checkpoint as LOCAL bind volumes on the
# workers (NFS_SHARE=0) — never touch the exporter then (it is unkillable and serves the
# censored dir; run 2 of the swap trial died on exactly that).
if grep -qE '^NFS_SHARE=0' "$KIT/.env.tp4"; then
  say "NFS_SHARE=0 (local worker volumes) — skipping share"
else
  ./start-tp4.sh share >>"$LOG" 2>&1 || say "share step reported an error (continuing)"
fi
# start-tp4.sh serve can hang after the engine prints Ready (readiness loop never exits,
# 2026-09-15 x3). Bound it; health is judged by the completion probe below, not by serve.
timeout 2700 ./start-tp4.sh serve >>"$LOG" 2>&1 || true
pkill -f "start.sh serve" 2>/dev/null || true
for i in $(seq 1 90); do
  if probe_ok; then
    say "RECOVERED: SGLang serving $MODEL on $API"
    # prewarm: the first real inference otherwise pays the Triton JIT cost (2026-09-14: 102 s cold)
    timeout 900 python3 /home/jun/dsv41-vllm/ops/prewarm.py "$API/v1" "$MODEL" >>"$LOG" 2>&1 \
      || say "prewarm: non-fatal failure (see log)"
    exit 0
  fi
  sleep 10
done
say "FAIL: world did not come back after stop + serve"
exit 1
