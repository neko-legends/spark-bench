#!/bin/bash
# launch-dsv41-tp4.sh — DeepSeek-V4.1-Flash NVMe-engram adapter, TP4+EP4 on 4x DGX Spark (GB10 sm_120)
# Run ON FORGE (rank 0). Orchestrates all 4 nodes.
#
# Derived from 0xSero's boot.py serve() args (bypassed: single-node asserts,
# forced >=400k context, RTX PRO 6000 check) + our qwen38/GLM fabric lessons:
#   - workers (rank 3,2,1) first, then head (rank 0), 15s apart
#   - ConnectX rail B env: enP2p1s0f1np1 / roceP2p1s0f1 / 192.168.10.0/24
#   - crash-log snapshot before any docker rm
#
# Env overrides: IMAGE, MEM_FRAC, CACHE_GIB, CONTEXT, SEQS, PORT, DIST_PORT,
#   KEEP_QWEN=1 (skip stopping qwen), NO_CUDA_GRAPH=1 (eager), EXTRA_ARGS,
#   SPEC_BS (dspark block size; 5=checkpoint default is CORRUPT on SM120/121 — sgl #33800; use 4),
#   SWA_REPLAY=0 (drop --enable-decoder-swa-bounded-replay)
#   CONTAINER.
set -uo pipefail

IMAGE=${IMAGE:-local/dsv41-gb10:p2}
CONTAINER=${CONTAINER:-dsv41-rank}
MODEL_HOST=/home/jun/models/deepseek-v4.1-flash
MODEL_DIR=/models/DeepSeek-V4.1-Flash
STATE_HOST=/home/jun/dsv41-state
LOGDIR=/home/jun/dsv41-port/logs

PORT=${PORT:-8000}
DIST_PORT=${DIST_PORT:-29500}
SERVED_MODEL_NAME=deepseek-v4.1-flash
HEAD_IP=192.168.10.1
TP=4
NNODES=4
MEM_FRAC=${MEM_FRAC:-0.80}
CACHE_GIB=${CACHE_GIB:-32}
CONTEXT=${CONTEXT:-131072}
SEQS=${SEQS:-4}
MEMORY_GIB=${MEMORY_GIB:-120}
SPEC_BS=${SPEC_BS:-5}
if [ "${SPEC:-1}" = "1" ]; then
  SPEC_ARGS="--speculative-algorithm DSPARK --speculative-dspark-block-size $SPEC_BS"
else
  SPEC_ARGS=""
fi
SWA=${SWA_REPLAY:-1}
[ "$SWA" = "1" ] && SWA_ARGS="--enable-decoder-swa-bounded-replay" || SWA_ARGS=""

IFACE=enP2p1s0f1np1
IB_HCA=roceP2p1s0f1
NCCL_IB_ADDR_RANGE=192.168.10.0/24

SSH_HOSTS=(local 192.168.10.2 192.168.10.3 192.168.10.4)
NODE_IPS=(192.168.10.1 192.168.10.2 192.168.10.3 192.168.10.4)

say() { echo "[dsv41-tp4] $*"; }

remote() {
  local h="$1"; shift
  if [ "$h" = local ]; then bash -c "$*"; else ssh -o BatchMode=yes -o ConnectTimeout=10 "$h" "$*"; fi
}

# ---------------- stop qwen (authorized 2026-09-10) ----------------
if [ "${KEEP_QWEN:-0}" != "1" ]; then
  for i in "${!SSH_HOSTS[@]}"; do
    h="${SSH_HOSTS[$i]}"
    remote "$h" "docker stop qwen38-nvfp4 >/dev/null 2>&1 && echo '  rank$i: qwen38-nvfp4 stopped' || echo '  rank$i: qwen38-nvfp4 not running'" &
  done; wait
else
  say "KEEP_QWEN=1 — skipping qwen stop (will OOM if it still holds memory!)"
fi

# ---------------- preflight ----------------
say "preflight: image $IMAGE, model $MODEL_HOST, port $PORT"
for i in "${!SSH_HOSTS[@]}"; do
  h="${SSH_HOSTS[$i]}"
  say "preflight rank$i ($h)"
  remote "$h" "
    set -e
    mkdir -p /home/jun/dsv41-crash-logs
    docker inspect $CONTAINER$i >/dev/null 2>&1 && docker logs --tail 4000 $CONTAINER$i > /home/jun/dsv41-crash-logs/\$(date +%Y%m%d-%H%M%S)-\$(hostname)-$CONTAINER$i.log 2>&1 || true
    docker rm -f $CONTAINER$i >/dev/null 2>&1 || true
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || { echo '  FAIL rank$i: nvidia-smi'; exit 1; }
    apps=\$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | grep -c . || true)
    [ \"\$apps\" = \"0\" ] || { echo \"  FAIL rank$i: \$apps GPU compute app(s) still running\"; exit 1; }
    test -f $MODEL_HOST/model.safetensors.index.json || { echo '  FAIL rank$i: model index missing'; exit 1; }
    docker image inspect $IMAGE >/dev/null 2>&1 || { echo \"  FAIL rank$i: image $IMAGE missing\"; exit 1; }
    mkdir -p $STATE_HOST
    echo '  preflight OK'
  " || { say "preflight FAILED on rank$i ($h)"; exit 1; }
done
# image ID identical fleet-wide
REF_ID=""
for i in "${!SSH_HOSTS[@]}"; do
  ID=$(remote "${SSH_HOSTS[$i]}" "docker image inspect $IMAGE --format '{{.Id}}' 2>/dev/null" || echo MISSING)
  [ -z "$REF_ID" ] && REF_ID="$ID"
  [ "$ID" != "$REF_ID" ] && { say "FAIL: image ID mismatch on rank$i"; exit 1; }
done
say "image ID identical on all 4 nodes: $REF_ID"

# ---------------- launch rank ----------------
launch_rank() {
  local rank="$1" h="$2" ip="$3"
  local head_args=""
  [ "$rank" = "0" ] && head_args="--host 0.0.0.0 --port $PORT"
  local cg=""
  [ "${NO_CUDA_GRAPH:-0}" = "1" ] && cg="--disable-cuda-graph"

  cat > /tmp/dsv41-docker-r$rank.sh << DR_EOF
#!/bin/bash
set -e
docker run -d --name $CONTAINER$rank --restart no \
  --log-driver json-file --log-opt max-size=25m --log-opt max-file=4 \
  --gpus all --network host --ipc=host --shm-size 32g --stop-timeout 60 \
  --memory ${MEMORY_GIB}g --memory-swap ${MEMORY_GIB}g \
  --device /dev/infiniband --cap-add IPC_LOCK --cap-add SYS_NICE \
  --ulimit memlock=-1 --ulimit stack=67108864 \
  --ulimit nofile=1048576:1048576 \
  -v $MODEL_HOST:$MODEL_DIR:ro \
  -v $STATE_HOST:/state \
  -e NODE_RANK=$rank \
  -e DSV41_SOURCE=$MODEL_DIR \
  -e OFFLOAD_MODE=nvme \
  -e DSV41_CACHE_GIB=$CACHE_GIB \
  -e SERVER_PORT=$PORT \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  -e HOST_IP=$ip -e SGLANG_HOST_IP=$ip \
  -e NCCL_NET=IB -e NCCL_IB_DISABLE=0 \
  -e NCCL_IB_ROCE_VERSION_NUM=2 -e NCCL_IB_ADDR_FAMILY=AF_INET \
  -e NCCL_IB_ADDR_RANGE=$NCCL_IB_ADDR_RANGE \
  -e NCCL_IB_HCA=$IB_HCA \
  -e NCCL_SOCKET_IFNAME=$IFACE -e GLOO_SOCKET_IFNAME=$IFACE -e TP_SOCKET_IFNAME=$IFACE \
  -e NCCL_CROSS_NIC=1 -e NCCL_NVLS_ENABLE=0 -e NCCL_IB_MERGE_NICS=0 -e NCCL_CUMEM_ENABLE=0 \
  -e NCCL_IGNORE_CPU_AFFINITY=1 -e NCCL_DEBUG=${NCCL_DEBUG:-WARN} \
  -e TORCH_NCCL_ASYNC_ERROR_HANDLING=1 \
  -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  --entrypoint python3 $IMAGE -m sglang.launch_server \
    --model-path $MODEL_DIR \
    --served-model-name $SERVED_MODEL_NAME \
    --trust-remote-code --load-format safetensors --tp $TP --ep-size $TP \
    --nnodes $NNODES --node-rank $rank --dist-init-addr ${HEAD_IP}:${DIST_PORT} \
    --attention-backend dsv4 --moe-runner-backend flashinfer_mxfp4 \
    --mem-fraction-static $MEM_FRAC \
    --chunked-prefill-size 2048 \
    --context-length $CONTEXT \
    --max-running-requests $SEQS \
    --cuda-graph-max-bs-decode $SEQS \
    --min-free-slots-delay 1 --random-seed 0 \
    ${SPEC_ARGS} ${SWA_ARGS} \
    --tool-call-parser deepseekv41 --reasoning-parser deepseek-v41 \
    $cg \
    ${EXTRA_ARGS:-} \
    $head_args
DR_EOF
  if [ "$h" = local ]; then
    bash /tmp/dsv41-docker-r$rank.sh >/dev/null
  else
    cat /tmp/dsv41-docker-r$rank.sh | ssh -o BatchMode=yes "$h" "cat > /tmp/dsv41-docker.sh && bash /tmp/dsv41-docker.sh" >/dev/null
  fi
  # tail container logs into the per-rank log file on that node
  # (NB: `A && B &` backgrounds a subshell that holds ssh's pipes open — hang;
  #  use `A; B &` with a trailing foreground echo — tested 2026-09-10)
  remote "$h" "mkdir -p $LOGDIR; setsid nohup docker logs -f $CONTAINER$rank > $LOGDIR/rank$rank.log 2>&1 < /dev/null & echo log-tail-started"
  remote "$h" "sleep 3; docker ps --format '{{.Names}}' | grep -x '$CONTAINER$rank' || { docker logs --tail 100 $CONTAINER$rank 2>&1; echo 'RANK $rank EXITED'; exit 1; }" || { say "rank$rank container exited at startup"; exit 1; }
  say "rank$rank up ($h) -> $LOGDIR/rank$rank.log"
}

# workers (3,2,1) first, then head (0), 15s apart
for rank in 3 2 1; do
  launch_rank "$rank" "${SSH_HOSTS[$rank]}" "${NODE_IPS[$rank]}"
  sleep 15
done
launch_rank 0 local "${NODE_IPS[0]}"

say "launched (mem=$MEM_FRAC cache=${CACHE_GIB}GiB ctx=$CONTEXT seqs=$SEQS)."
say "ready when: curl -s http://${HEAD_IP}:${PORT}/v1/models"
if [ "${1:-}" = "--wait" ]; then
  for i in $(seq 1 120); do
    curl -sf -m 5 "http://${HEAD_IP}:${PORT}/v1/models" >/dev/null 2>&1 && { say "READY after ~$((i*30))s"; exit 0; }
    sleep 30
  done
  say "TIMEOUT after 3600s — check: ssh <rank> docker logs --tail 200 $CONTAINER<r>"
  exit 1
fi
