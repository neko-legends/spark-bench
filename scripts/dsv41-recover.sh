#!/bin/bash
# dsv41-recover.sh — one-command recovery for the DeepSeek-V4.1-Flash TP4 vLLM world.
#
# Run ON FORGE (rank 0). Use after a node reboot (or any time the world is wedged)
# to bring the four-node TP4 world back to the champion config without hand-typing
# the launcher env. Idempotent: running it twice converges to the same state; a
# flock prevents two concurrent runs.
#
#   bash /home/jun/git/spark-bench/scripts/dsv41-recover.sh
#
# What it does, in order:
#   1. verify all 4 nodes reachable over the fabric (ssh)
#   2. verify spark-gpu-clock-lock is active on every node
#   3. stop any existing vllm_dsv41 container HEAD-FIRST on all 4 nodes
#   4. wait for GPU compute apps on every node to drain
#   5. relaunch with the champion values from CHAMPION.env (disarmed boot →
#      API up → spec gate → the launcher arms unless-stopped)
#   6. wait for /v1/models to list deepseek-v4.1-flash, then arm every rank
#
# This script never touches /home/jun/models, other containers, or the other
# lanes (SGLang / qwen). It does not reboot nodes. It only manages vllm_dsv41.
set -uo pipefail

CHAMPION_ENV=${CHAMPION_ENV:-/home/jun/dsv41-vllm/CHAMPION.env}
LAUNCHER=${LAUNCHER:-/home/jun/launch-dsv41-vllm-tp4.sh}
CONTAINER=${CONTAINER:-vllm_dsv41}
MODEL=${MODEL:-deepseek-v4.1-flash}
HEAD_IP=${HEAD_IP:-192.168.10.1}
PORT=${PORT:-8000}
LOCK_SERVICE=${LOCK_SERVICE:-spark-gpu-clock-lock}
API_URL="http://${HEAD_IP}:${PORT}/v1/models"
WAIT_SECS=${WAIT_SECS:-2400}
DRAIN_SECS=${DRAIN_SECS:-90}
LOCK_FILE=${LOCK_FILE:-/tmp/dsv41-recover.lock}

SSH_HOSTS=(local 192.168.10.2 192.168.10.3 192.168.10.4)
NODE_NAMES=(forge anvil ember flame)

say() { echo "[dsv41-recover] $*"; }
fail() { say "FAIL: $*"; exit 1; }

remote() {
  local h="$1"; shift
  if [ "$h" = local ]; then bash -c "$*"; else ssh -o BatchMode=yes -o ConnectTimeout=10 "$h" "$*"; fi
}

# Single-instance guard: a second invocation exits immediately rather than
# racing the first one's stop/relaunch.
exec 9>"$LOCK_FILE" || fail "cannot open lock file $LOCK_FILE"
if ! flock -n 9; then
  say "another dsv41-recover run holds $LOCK_FILE — nothing to do."
  exit 0
fi

# Must run on forge: this host is the only one that reaches the 192.168.10.x
# fabric addresses and the head rank lives here.
if [ "${ALLOW_NON_FORGE:-0}" != "1" ] && [ "$(hostname)" != "forge" ]; then
  fail "run this on forge (hostname is '$(hostname)'); set ALLOW_NON_FORGE=1 only for a dry check"
fi

[ -f "$CHAMPION_ENV" ] || fail "champion env not found: $CHAMPION_ENV"
[ -f "$LAUNCHER" ] || fail "launcher not found: $LAUNCHER"

# ---- 1. reachability ----
say "1/6 checking node reachability..."
for i in "${!SSH_HOSTS[@]}"; do
  h="${SSH_HOSTS[$i]}"
  if ! remote "$h" "echo reachable" >/dev/null 2>&1; then
    fail "node ${NODE_NAMES[$i]} ($h) is NOT reachable — fix the node/network before recovering"
  fi
  say "  ${NODE_NAMES[$i]}: reachable"
done

# ---- 2. clock lock ----
say "2/6 checking $LOCK_SERVICE on all nodes..."
for i in "${!SSH_HOSTS[@]}"; do
  h="${SSH_HOSTS[$i]}"
  state="$(remote "$h" "systemctl is-active $LOCK_SERVICE" 2>/dev/null | tr -d '[:space:]')"
  if [ "$state" != "active" ]; then
    fail "${NODE_NAMES[$i]}: $LOCK_SERVICE is '$state' (expected active). Start it: ssh ${NODE_NAMES[$i]} 'sudo systemctl start $LOCK_SERVICE'"
  fi
  say "  ${NODE_NAMES[$i]}: clock lock active"
done

# ---- 3. stop existing container, HEAD FIRST ----
say "3/6 stopping any $CONTAINER (head first)..."
for i in 0 1 2 3; do
  h="${SSH_HOSTS[$i]}"
  remote "$h" "timeout 90 docker rm -f $CONTAINER >/dev/null 2>&1 || true" || true
  say "  ${NODE_NAMES[$i]}: container cleared"
done

# ---- 4. wait for GPU compute apps to drain (post-reboot / post-stop) ----
say "4/6 waiting for GPU compute apps to drain (max ${DRAIN_SECS}s)..."
deadline=$(( $(date +%s) + DRAIN_SECS ))
for i in "${!SSH_HOSTS[@]}"; do
  h="${SSH_HOSTS[$i]}"
  while :; do
    apps="$(remote "$h" "nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | grep -c ." 2>/dev/null | tr -d '[:space:]')"
    [ "${apps:-0}" = "0" ] && break
    if [ "$(date +%s)" -ge "$deadline" ]; then
      fail "${NODE_NAMES[$i]}: $apps GPU compute app(s) still running after ${DRAIN_SECS}s"
    fi
    sleep 5
  done
  say "  ${NODE_NAMES[$i]}: GPU idle"
done

# ---- 5. relaunch with champion values ----
say "5/6 relaunching with $CHAMPION_ENV ..."
set -a
# shellcheck disable=SC1090
. "$CHAMPION_ENV"
set +a
say "  MAXLEN=${MAXLEN:-?} GMU=${GMU:-?} SEQS=${SEQS:-?} SPEC_K=${SPEC_K:-?} DRAFT_METHOD=${DRAFT_METHOD:-?} ENGRAM_THREADS=${ENGRAM_THREADS:-?} MAX_BATCHED=${MAX_BATCHED:-?}"
if ! bash "$LAUNCHER"; then
  fail "launcher exited non-zero — inspect 'docker logs $CONTAINER' on forge (head) and the launcher output above"
fi

# ---- 6. confirm the API, then arm ----
say "6/6 waiting for $API_URL ..."
deadline=$(( $(date +%s) + WAIT_SECS ))
up=0
while [ "$(date +%s)" -lt "$deadline" ]; do
  if curl -fsS --max-time 5 "$API_URL" 2>/dev/null | grep -q "$MODEL"; then up=1; break; fi
  sleep 10
done
[ "$up" = 1 ] || fail "API did not list $MODEL within ${WAIT_SECS}s"
say "  API is up and serving $MODEL."

say "arming auto-restart (unless-stopped) on all ranks..."
for i in "${!SSH_HOSTS[@]}"; do
  remote "${SSH_HOSTS[$i]}" "docker update --restart=unless-stopped $CONTAINER >/dev/null 2>&1 || true" || true
done

say "RECOVERED: TP4 vLLM world is UP at http://${HEAD_IP}:${PORT}/v1 ($MODEL)"
