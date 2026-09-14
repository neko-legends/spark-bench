#!/bin/bash
# launch-dsv41-vllm-tp4.sh — DeepSeek-V4.1-Flash on vLLM (dsv41-feat lineage), TP4 on 4x DGX Spark.
# Run ON FORGE (rank 0). Orchestrates all 4 nodes. Workers (rank 3,2,1) first, then head (rank 0).
#
# Recipe: tonyd2wild/DeepSeek-V4.1-Flash-vLLM-DGX-Spark @ ca662ac (boot 10), translated to our fabric:
#   - fabric: RoCE rail B 192.168.10.0/24, IFACE enP2p1s0f1np1, HCA roceP2p1s0f1, GID auto (ember/flame lesson)
#   - model: full local checkpoint on every node (/home/jun/models/deepseek-v4.1-flash) — NO NFS,
#     NO ENGRAM_LOCAL copy (every rank reads weights AND engram rows from local NVMe)
#   - our serving hardening: disarmed boot (restart no) -> API up -> spec gate -> arm unless-stopped
#   - Tony's relaunch rule: stop every node first, HEAD FIRST (stale head rendezvous fix)
#
# Env overrides: IMAGE (default local/vllm-dsv41:overlay5), MAXLEN (default 131072; raise to 300000
#   after gates), SEQS (8), GMU (0.80), SPEC_K (5), EAGER=1, PORT (8000), MPORT (29500),
#   CONTAINER (vllm_dsv41), PATCH_NAME (dsv41-boot10), ARM=1 to auto-arm after gate (default 1).
set -uo pipefail

IMAGE=${IMAGE:-local/vllm-dsv41:overlay5}
CONTAINER=${CONTAINER:-vllm_dsv41}
PATCH_NAME=${PATCH_NAME:-dsv41-boot10}
MODEL_HOST=${MODEL_HOST:-/home/jun/models/deepseek-v4.1-flash}
MODEL_DIR=${MODEL_DIR:-/models/DeepSeek-V4.1-Flash}
CACHE_HOST_PATH=/var/tmp/dsv41-vllm-cache
SITE=/usr/local/lib/python3.12/dist-packages/vllm
EXP_NAME=${EXP_NAME:-phase3}

PORT=${PORT:-8000}
MPORT=${MPORT:-29500}
HEAD_IP=192.168.10.1
SERVED_MODEL_NAME=${SERVED_MODEL_NAME:-deepseek-v4.1-flash}

GMU=${GMU:-0.80}
MAXLEN=${MAXLEN:-300000}
SEQS=${SEQS:-8}
MAX_BATCHED=${MAX_BATCHED:-8192}
SPEC_K=${SPEC_K:-5}
DRAFT_METHOD=${DRAFT_METHOD:-probabilistic}
ENGRAM_THREADS=${ENGRAM_THREADS:-32}
EXTRA_ENV_ARGS=${EXTRA_ENV_ARGS:-}
CPUS=${CPUS:-}
if [ -n "$CPUS" ]; then DOCKER_CPUS="--cpuset-cpus $CPUS"; else DOCKER_CPUS=""; fi
COMPILE_PASS=${COMPILE_PASS:-}
EAGER=${EAGER:-0}
CUDAGRAPH_MODE=${CUDAGRAPH_MODE:-FULL_AND_PIECEWISE}
MEMORY_GIB=${MEMORY_GIB:-112}
VLLM_EXTRA=${VLLM_EXTRA:-}
WAIT_SECS=${WAIT_SECS:-2400}

SSH_HOSTS=(local 192.168.10.2 192.168.10.3 192.168.10.4)
NODE_IPS=(192.168.10.1 192.168.10.2 192.168.10.3 192.168.10.4)
NODE_NAMES=(forge anvil ember flame)

IFACE=enP2p1s0f1np1
IB_HCA=roceP2p1s0f1

say() { echo "[dsv41-vllm-tp4] $*"; }

remote() {
  local h="$1"; shift
  if [ "$h" = local ]; then bash -c "$*"; else ssh -o BatchMode=yes -o ConnectTimeout=10 "$h" "$*"; fi
}

# ---- 1. stop everything first, HEAD FIRST (Tony fix #6: stale head rendezvous) ----
say "stopping any $CONTAINER on all nodes (head first)..."
for i in 0 1 2 3; do
  h=${SSH_HOSTS[$i]}
  remote "$h" "mkdir -p /home/jun/dsv41-crash-logs && \
    docker inspect $CONTAINER >/dev/null 2>&1 && docker logs --tail 4000 $CONTAINER > /home/jun/dsv41-crash-logs/\$(date +%Y%m%d-%H%M%S)-${NODE_NAMES[$i]}.log 2>&1 || true; \
    docker rm -f $CONTAINER >/dev/null 2>&1 || true"
done

# ---- 2. preflight per node ----
say "preflight: image=$IMAGE model=$MODEL_HOST patches=~/patches/$PATCH_NAME"
for i in "${!SSH_HOSTS[@]}"; do
  h="${SSH_HOSTS[$i]}"
  say "preflight rank$i (${NODE_NAMES[$i]})"
  remote "$h" "
    set -e
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader >/dev/null || { echo '  FAIL rank$i: nvidia-smi'; exit 1; }
    apps=\$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | grep -c . || true)
    [ \"\$apps\" = \"0\" ] || { echo \"  FAIL rank$i: \$apps GPU compute app(s) running\"; exit 1; }
    test -f $MODEL_HOST/model.safetensors.index.json || { echo '  FAIL rank$i: model index missing'; exit 1; }
    test -f $MODEL_HOST/model-00048-of-00048.safetensors || { echo '  FAIL rank$i: shard 48 missing'; exit 1; }
    docker image inspect $IMAGE >/dev/null 2>&1 || { echo '  FAIL rank$i: image $IMAGE missing'; exit 1; }
    test -f \$HOME/patches/$PATCH_NAME/mounts.txt || { echo '  FAIL rank$i: patches missing'; exit 1; }
    while read -r f rel; do
      [ -z \"\$f\" ] && continue
      test -f \$HOME/patches/$PATCH_NAME/\$f || { echo \"  FAIL rank$i: patch file \$f missing\"; exit 1; }
    done < \$HOME/patches/$PATCH_NAME/mounts.txt
    mkdir -p $CACHE_HOST_PATH
    avail=\$(awk '/^MemAvailable:/{print int(\$2/1048576)}' /proc/meminfo)
    [ \"\$avail\" -ge 100 ] || { echo \"  FAIL rank$i: MemAvailable \${avail}GiB < 100\"; exit 1; }
    echo '  preflight OK (avail '\$avail' GiB)'
  " || { say "preflight FAILED on rank$i (${NODE_NAMES[$i]})"; exit 1; }
done
# image ID identical fleet-wide
REF_ID=""
for i in "${!SSH_HOSTS[@]}"; do
  ID=$(remote "${SSH_HOSTS[$i]}" "docker image inspect $IMAGE --format '{{.Id}}' 2>/dev/null" || echo MISSING)
  [ "$ID" = MISSING ] && { say "FAIL: image missing on rank$i"; exit 1; }
  [ -z "$REF_ID" ] && REF_ID="$ID"
  [ "$ID" != "$REF_ID" ] && say "NOTE: image ID differs on rank$i ($ID vs $REF_ID) — node-local builds; verify5 no-JIT gate is the real check"
done
say "per-node image IDs recorded (head: $REF_ID)"

# ---- 3. graph sizes: exact multiples of k and k+1 up to SEQS*(k+1) ----
K=$SPEC_K
CG_SIZES=$( { seq "$K" "$K" $((K * SEQS)); seq $((K + 1)) $((K + 1)) $(((K + 1) * SEQS)); } | sort -n -u | paste -sd, - )
if [ "$EAGER" = "1" ]; then
  GRAPH_ARGS=(--enforce-eager)
  GRAPH_ENV=""
else
  GRAPH_ARGS=(--compilation-config "{\"cudagraph_mode\":\"$CUDAGRAPH_MODE\",\"cudagraph_capture_sizes\":[$CG_SIZES]$COMPILE_PASS}")
  GRAPH_ENV="-e VLLM_USE_BREAKABLE_CUDAGRAPH=1"
fi
SPEC_ARGS="--speculative-config {\"method\":\"dspark\",\"num_speculative_tokens\":$K,\"draft_sample_method\":\"$DRAFT_METHOD\",\"rejection_sample_method\":\"block\",\"enable_adaptive_verification\":false}"

# ---- 4. launch one rank ----
launch_rank() {
  local rank="$1" h="$2" ip="$3"
  local headless=""
  [ "$rank" != "0" ] && headless="--headless"
  cat > /tmp/dsv41-vllm-r$rank.sh << LR_EOF
#!/bin/bash
set -e
PATCH_MOUNTS=""
while read -r f rel; do
  [ -z "\$f" ] && continue
  test -f \$HOME/patches/$PATCH_NAME/\$f || { echo "PATCH FILE MISSING: \$f"; exit 3; }
  PATCH_MOUNTS="\$PATCH_MOUNTS -v \$HOME/patches/$PATCH_NAME/\$f:$SITE/\$rel:ro"
done < \$HOME/patches/$PATCH_NAME/mounts.txt
mkdir -p $CACHE_HOST_PATH
if [ -n "$CPUS" ]; then DOCKER_CPUS="--cpuset-cpus $CPUS"; else DOCKER_CPUS=""; fi
if [ "$EAGER" = "1" ]; then
  GRAPH_ARGS=(--enforce-eager)
else
  GRAPH_ARGS=(--compilation-config "{\"cudagraph_mode\":\"$CUDAGRAPH_MODE\",\"cudagraph_capture_sizes\":[$CG_SIZES]$COMPILE_PASS}")
fi
SPEC_ARGS="--speculative-config {\"method\":\"dspark\",\"num_speculative_tokens\":$K,\"draft_sample_method\":\"$DRAFT_METHOD\",\"rejection_sample_method\":\"block\",\"enable_adaptive_verification\":false}"
docker run -d --name $CONTAINER --restart no \
  --log-driver json-file --log-opt max-size=25m --log-opt max-file=4 \
  --gpus all --network host --ipc host --shm-size 32g --stop-timeout 60 \
  --memory ${MEMORY_GIB}g --memory-swap ${MEMORY_GIB}g --oom-score-adj 500 \
  --device /dev/infiniband --cap-add IPC_LOCK --cap-add SYS_NICE \
  --ulimit memlock=-1 --ulimit stack=67108864 --ulimit nofile=1048576:1048576 \
  -v $MODEL_HOST:$MODEL_DIR:ro \
  -v $CACHE_HOST_PATH:/cache \
  \$PATCH_MOUNTS \
  -e VLLM_HOST_IP=$ip -e HF_HOME=/cache/huggingface -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  -e VLLM_CACHE_ROOT=/cache/vllm-$EXP_NAME \
  -e VLLM_ENGINE_READY_TIMEOUT_S=3600 -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  -e VLLM_USE_RUST_FRONTEND=0 -e VLLM_HAS_FLASHINFER_CUBIN=1 \
  -e DSV41_ENGRAM_DISK=1 -e DSV41_ENGRAM_DISK_THREADS=$ENGRAM_THREADS -e DSV41_ENGRAM_DISK_CHUNK=16 \
  $GRAPH_ENV \
  -e TORCH_CUDA_ARCH_LIST=12.1a -e FLASHINFER_CUDA_ARCH_LIST=12.1a -e FLASHINFER_DISABLE_VERSION_CHECK=1 \
  -e NCCL_NET=IB -e NCCL_IB_DISABLE=0 -e NCCL_IB_HCA=$IB_HCA -e NCCL_IB_GID_INDEX=auto \
  -e NCCL_IB_ROCE_VERSION_NUM=2 -e NCCL_IB_ADDR_FAMILY=AF_INET -e NCCL_IB_ADDR_RANGE=192.168.10.0/24 \
  -e NCCL_SOCKET_IFNAME=$IFACE -e GLOO_SOCKET_IFNAME=$IFACE -e TP_SOCKET_IFNAME=$IFACE -e MN_IF_NAME=$IFACE \
  -e NCCL_NVLS_ENABLE=0 -e NCCL_CROSS_NIC=1 -e NCCL_IB_MERGE_NICS=0 -e NCCL_CUMEM_ENABLE=0 \
  -e NCCL_IGNORE_CPU_AFFINITY=1 -e NCCL_DEBUG=WARN -e TORCH_NCCL_ASYNC_ERROR_HANDLING=1 \
  -e TORCH_NCCL_HEARTBEAT_TIMEOUT_SEC=180 \
  -e MAX_JOBS=2 -e FLASHINFER_NVCC_THREADS=1 -e VLLM_USE_FLASHINFER_SAMPLER=0 \
  -e TILELANG_CACHE_DIR=/cache/tilelang -e TRITON_CACHE_DIR=/cache/triton \
  $EXTRA_ENV_ARGS $DOCKER_CPUS \
  "$IMAGE" \\
    $MODEL_DIR \\
    --served-model-name $SERVED_MODEL_NAME --host 0.0.0.0 --port $PORT \\
    --tensor-parallel-size 4 --gpu-memory-utilization $GMU --max-model-len $MAXLEN \\
    --max-num-seqs $SEQS --max-num-batched-tokens $MAX_BATCHED \\
    --block-size 128 \\
    --engram-config '{"cpu_offload": false}' \\
    --default-chat-template-kwargs '{"thinking": true}' \\
    --limit-mm-per-prompt '{"image":4}' --mm-processor-cache-gb 1 \\
    --tool-call-parser deepseek_v41 --enable-auto-tool-choice --reasoning-parser deepseek_v41 \\
    \$SPEC_ARGS "\${GRAPH_ARGS[@]}" \\
    --distributed-executor-backend mp --nnodes 4 --node-rank $rank \\
    --master-addr $HEAD_IP --master-port $MPORT $headless $VLLM_EXTRA
echo "launched rank=$rank image=$IMAGE gmu=$GMU maxlen=$MAXLEN seqs=$SEQS eager=$EAGER cg=${CUDAGRAPH_MODE}[${CG_SIZES}] spec_k=$K"
LR_EOF
  remote "$h" "bash -s" < /tmp/dsv41-vllm-r$rank.sh
}

# workers 3,2,1 then head 0 (15s apart)
for rank in 3 2 1; do
  say "launching rank$rank (${NODE_NAMES[$rank]})"
  launch_rank "$rank" "${SSH_HOSTS[$rank]}" "${NODE_IPS[$rank]}"
  sleep 15
done
say "launching rank0 head (forge)"
launch_rank 0 "${SSH_HOSTS[0]}" "${NODE_IPS[0]}"

# ---- 5. disarmed wait: API up, then spec gate, then arm ----
API_URL="http://192.168.10.1:$PORT/v1/models"
say "waiting for API at $API_URL (restart stays DISARMED)..."
up=0
for i in $(seq 1 $((WAIT_SECS / 10))); do
  if curl -fsS --max-time 5 "$API_URL" >/dev/null 2>&1; then up=1; break; fi
  if [ $((i % 12)) = 0 ]; then
    say "  still waiting ($((i*10))s)... head tail:"
    remote local "docker logs --tail 6 $CONTAINER 2>&1 | tail -6" || true
  fi
  if ! remote local "docker inspect -f {{.State.Running}} $CONTAINER 2>/dev/null" | grep -q true; then
    say "HEAD CONTAINER DIED. Last 40 log lines:"
    remote local "docker logs --tail 40 $CONTAINER 2>&1" || true
    for r in 1 2 3; do remote "${SSH_HOSTS[$r]}" "docker rm -f $CONTAINER >/dev/null 2>&1 || true"; done
    exit 1
  fi
  sleep 10
done
[ $up = 1 ] || { say "API did not come up in ${WAIT_SECS}s"; remote local "docker logs --tail 60 $CONTAINER"; exit 1; }
say "API is up."

# warm one real request so spec metrics appear
curl -fsS --max-time 120 http://192.168.10.1:$PORT/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"'$SERVED_MODEL_NAME'","messages":[{"role":"user","content":"Count from 1 to 10."}],"max_tokens":40,"temperature":0,"chat_template_kwargs":{"thinking":false}}' >/dev/null 2>&1 || true
sleep 15

say "running spec-decode gate..."
gate_fail() {
  say "GATE FAIL: $1. Stopping all ranks; auto-restart stays DISARMED."
  for i in 0 1 2 3; do remote "${SSH_HOSTS[$i]}" "docker stop $CONTAINER >/dev/null 2>&1 || true"; done
  exit 1
}
metrics="$(curl -fsS --max-time 10 "http://192.168.10.1:$PORT/metrics" 2>/dev/null || true)"
spec_lines=$(grep -c "spec" <<<"$metrics" || true)
accepted=""
if [ "${spec_lines:-0}" -gt 0 ]; then
  accepted=$(remote local "docker logs --since 5m $CONTAINER 2>&1 | grep -c 'SpecDecoding metrics'" || true)
fi
if [ "${accepted:-0}" -gt 0 ] || grep -q "spec_decode" <<<"$metrics"; then
  say "OK: speculative decoding live (metrics spec matches=$spec_lines, log SpecDecoding lines=$accepted)"
else
  gate_fail "no spec-decode evidence in /metrics or head log"
fi

if [ "${ARM:-1}" = "1" ]; then
  say "arming auto-restart (unless-stopped) on all ranks..."
  for i in 0 1 2 3; do remote "${SSH_HOSTS[$i]}" "docker update --restart=unless-stopped $CONTAINER >/dev/null"; done
fi
if [ "${PREWARM:-1}" = "1" ]; then
  say "prewarm: exercising DSpark/Triton kernels + tool path before declaring UP (PREWARM=0 to skip)..."
  timeout 900 python3 /home/jun/dsv41-vllm/ops/prewarm.py "http://127.0.0.1:$PORT/v1" "$SERVED_MODEL_NAME" 2>&1 | sed "s/^/  /" || say "prewarm: non-fatal failure (see above)"
fi
say "TP4 vLLM world is UP: http://192.168.10.1:$PORT/v1 (model $SERVED_MODEL_NAME, max_model_len $MAXLEN)"
