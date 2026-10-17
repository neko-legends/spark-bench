#!/usr/bin/env bash
# launch-glm53-fp4-tp4.sh — nvidia/GLM-5.3-Flash-FP4-Local on 4x DGX Spark, TP-4, vLLM (community b12x image, the
# model card's required container). Card flags verbatim except the topology (TP 4 / nnodes 4) and the fabric pinning
# (rail B only: HCA roceP2p1s0f1, iface enP2p1s0f1np1, <rail-B-subnet>/24; never the dark f0 ports; GID auto).
#   launch-glm53-fp4-tp4.sh start | stop | status | logs [host]
set -uo pipefail
IMAGE=${IMAGE:-glm53-fp4-vllm:b12x-20261015}
NAME=glm53-fp4
MODEL_HOST=$HOME/models/GLM-5.3-Flash-FP4-Local
SERVED=${SERVED:-GLM-5.3-Flash-FP4}
PORT=${PORT:-18888}
MASTER_PORT=${MASTER_PORT:-29531}
HEAD_IP=<rail-B-ip>
HOSTS=(spark1 <rail-B-ip> <rail-B-ip> <rail-B-ip>)
MAX_MODEL_LEN=${MAX_MODEL_LEN:-500000}
MAX_NUM_SEQS=${MAX_NUM_SEQS:-4}
MAX_BATCHED=${MAX_BATCHED:-4096}
GPU_UTIL=${GPU_UTIL:-0.87}
SPEC_TOKENS=${SPEC_TOKENS:-5}
NEED_GB=${NEED_GB:-100}
say() { echo "[glm53-fp4 $(date +%T)] $*"; }
r() { local h=$1; shift; if [ "$h" = spark1 ]; then bash -c "$*"; else ssh -o BatchMode=yes -o ConnectTimeout=10 "$h" "$*"; fi; }

INNER='set -e
export CUTE_DSL_ARCH=sm_121a SAFETENSORS_FAST_GPU=1 VLLM_ENABLE_ROCE_ALLREDUCE=1 VLLM_ROCE_ALLREDUCE_MAX_SIZE=2MB \
  NCCL_BUFFSIZE=1048576 NCCL_MAX_CTAS=8 VLLM_WORKER_MULTIPROC_METHOD=spawn VLLM_SSM_CONV_STATE_LAYOUT=DS \
  VLLM_USE_AOT_COMPILE=1 VLLM_USE_MEGA_AOT_ARTIFACT=1 VLLM_USE_V2_MODEL_RUNNER=1 VLLM_ENABLE_PCIE_ALLREDUCE=0 \
  B12X_POLICY_MODE=auto VLLM_B12X_MOE_FP4_FORCE_A16=1 B12X_W4A16_A4_PREFILL=1
A=(/models/glm53 --served-model-name "$SERVED" --host 0.0.0.0 --port "$PORT" --tensor-parallel-size 4
  --mamba-cache-mode align --enable-prefix-caching --enable-chunked-prefill --dtype bfloat16 --kv-cache-dtype fp8
  --quantization modelopt_mixed --attention-backend B12X --block-size 256 --moe-backend b12x --linear-backend b12x
  --no-enable-flashinfer-autotune --load-format b12x --max-model-len "$MAX_MODEL_LEN" --max-num-seqs "$MAX_NUM_SEQS"
  --max-num-batched-tokens "$MAX_BATCHED"
  --speculative-config "{\"method\":\"mtp\",\"num_speculative_tokens\":$SPEC_TOKENS,\"moe_backend\":\"humming\",\"attention_backend\":\"B12X\"}"
  --reasoning-parser glm45 --tool-call-parser glm47 --enable-auto-tool-choice --gpu-memory-utilization "$GPU_UTIL"
  --nnodes 4 --node-rank "$NODE_RANK" --master-addr "$HEAD_IP" --master-port "$MASTER_PORT")
[ "$NODE_RANK" != 0 ] && A+=(--headless)
[ -f /glm53cfg/chat_template.thinkswitch.jinja ] && A+=(--chat-template /glm53cfg/chat_template.thinkswitch.jinja)
[ -n "${EXTRA_ARGS:-}" ] && A+=($EXTRA_ARGS)
echo "[r$NODE_RANK] vllm serve ${A[*]}"
exec vllm serve "${A[@]}"'

start() {
  for i in 0 1 2 3; do h=${HOSTS[$i]}
    r $h "docker rm -f $NAME-r$i >/dev/null 2>&1; sync; a=\$(awk '/MemAvailable/{print int(\$2/1048576)}' /proc/meminfo); echo \"$h avail \${a}GiB\"; [ \$a -ge $NEED_GB ] && [ -f $MODEL_HOST/config.json ]" \
      || { say "preflight FAILED on $h (memory < ${NEED_GB} GiB or weights missing)"; return 1; }
  done
  for i in 3 2 1 0; do h=${HOSTS[$i]}
    gid=$(r $h "d=/sys/class/infiniband/roceP2p1s0f1/ports/1; for g in \$(ls \$d/gids); do case \$(cat \$d/gids/\$g 2>/dev/null) in 0000:0000:0000:0000:0000:ffff:c0a8:0a*) [ \"\$(cat \$d/gid_attrs/types/\$g 2>/dev/null)\" = \"RoCE v2\" ] && echo \$g;; esac; done | head -1")
    [ -n "$gid" ] || { say "no RoCEv2 IPv4 GID on $h"; return 1; }; say "$h RoCEv2 GID index $gid"
    r $h "mkdir -p ~/.cache/glm53-fp4/{vllm,flashinfer,triton,b12x,hf}; docker run -d --rm --name $NAME-r$i --privileged --gpus all --ipc host --network host \
      --shm-size=16g --ulimit nofile=1048576:1048576 --ulimit memlock=-1 --ulimit stack=67108864 \
      --device /dev/infiniband \
      -e NODE_RANK=$i -e HEAD_IP=$HEAD_IP -e MASTER_PORT=$MASTER_PORT -e SERVED=$SERVED -e PORT=$PORT \
      -e MAX_MODEL_LEN=$MAX_MODEL_LEN -e MAX_NUM_SEQS=$MAX_NUM_SEQS -e MAX_BATCHED=$MAX_BATCHED -e GPU_UTIL=$GPU_UTIL -e SPEC_TOKENS=$SPEC_TOKENS \
      -e EXTRA_ARGS='${EXTRA_ARGS:-}' \
      -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 -e VLLM_HOST_IP=<rail-B-ip>$((i+1)) \
      -e MN_IF_NAME=enP2p1s0f1np1 -e UCX_NET_DEVICES=enP2p1s0f1np1 -e NCCL_SOCKET_IFNAME=enP2p1s0f1np1 \
      -e NCCL_IB_HCA=roceP2p1s0f1 -e NCCL_IB_DISABLE=0 -e NCCL_IB_GID_INDEX=-1 -e B12X_ROCE_GID_INDEX=$gid -e B12X_ROCE_HCA=roceP2p1s0f1 -e NCCL_IB_ADDR_RANGE=<rail-B-subnet>/24 \
      -e OMPI_MCA_btl_tcp_if_include=enP2p1s0f1np1 -e GLOO_SOCKET_IFNAME=enP2p1s0f1np1 -e TP_SOCKET_IFNAME=enP2p1s0f1np1 \
      -e NCCL_IGNORE_CPU_AFFINITY=1 -e NCCL_DEBUG=WARN \
      -v $MODEL_HOST:/models/glm53:ro -v \$HOME/glm53-fp4:/glm53cfg:ro \
      -v \$HOME/.cache/glm53-fp4/vllm:/root/.cache/vllm -v \$HOME/.cache/glm53-fp4/flashinfer:/root/.cache/flashinfer \
      -v \$HOME/.cache/glm53-fp4/triton:/root/.triton -v \$HOME/.cache/glm53-fp4/b12x:/root/.cache/b12x \
      -v \$HOME/.cache/glm53-fp4/hf:/root/.cache/huggingface \
      --entrypoint /bin/bash $IMAGE -c '$INNER' >/dev/null && echo \"$h r$i started\"" || { say "docker run failed on $h"; return 1; }
    sleep 3
  done
  say "waiting for spark1:$PORT/v1/models"
  for k in $(seq 1 240); do
    curl -s -m 5 http://127.0.0.1:$PORT/v1/models 2>/dev/null | grep -q "$SERVED" && { say "READY after $((k*10)) s"; return 0; }
    for i in 0 1 2 3; do r ${HOSTS[$i]} "docker ps -q --filter name=$NAME-r$i | grep -q ." || { say "rank $i container gone"; return 1; }; done
    sleep 10
  done; say "not ready after 2400 s"; return 1
}
stop() { for i in 0 1 2 3; do r ${HOSTS[$i]} "docker stop -t 60 $NAME-r$i >/dev/null 2>&1; echo ${HOSTS[$i]} left=\$(docker ps -q --filter name=$NAME | wc -l)"; done; }
status() { for i in 0 1 2 3; do r ${HOSTS[$i]} "echo ${HOSTS[$i]}: \$(docker ps --filter name=$NAME --format '{{.Names}} {{.Status}}')"; done; curl -s -m 5 http://127.0.0.1:$PORT/v1/models; echo; }
logs() { i=${1:-0}; r ${HOSTS[$i]} "docker logs --tail ${TAIL:-80} $NAME-r$i 2>&1"; }
case "${1:-status}" in start) start;; stop) stop;; status) status;; logs) logs "${2:-0}";; *) echo "usage: $0 start|stop|status|logs [rank]";; esac
