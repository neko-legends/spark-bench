#!/bin/bash
# GLM-5.3-Flash EXL3 TR3 4bpw + DFlash2 k=7 — TP4 on 4x DGX Spark
# Adapted from MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks (TP2 recipe) for this
# cluster: rail B fabric 192.168.10.0/24, HCA roceP2p1s0f1, if enP2p1s0f1np1.
# NCCL: pip 2.30.7 preloaded (image torch NCCL 2.29.7 breaks on this fabric),
# GID auto-detect (GID index differs per node on this fabric).
set -uo pipefail

IMAGE=ghcr.io/miaai-lab/glm-5.3-flash-2x-dgx-sparks:exl3
CONTAINER=glm53-uncens-exl3
MODEL_HOST=/home/jun/models/glm-5.3-flash-uncensored-exl3
DFLASH_HOST=/home/jun/models/glm-5.3-flash-dflash2
VLLM_CACHE_HOST=/var/tmp/glm53-exl3-vllm-cache
NCCL_HOST="$HOME/nccl-2.30.7"
NCCL_SO=libnccl.so.2.30.7

PORT=18888
MASTER_PORT=25000
SERVED_MODEL_NAME=GLM-5.3-Flash-UNCENSORED-EXL3
HEAD_IP=192.168.10.1
TP=4
NNODES=4
QUANTIZATION=exl3
MAX_MODEL_LEN=1000000
GPU_MEM_UTIL=0.82
MAX_NUM_SEQS=4
MAX_NUM_BATCHED_TOKENS=1024
KV_CACHE_DTYPE=fp8
SPEC_METHOD=dflash
DFLASH_TOKENS=7
DFLASH_DRAFT_TP=1
DFLASH_MODEL_DIR=/models/dflash2
MODEL_DIR=/models/exl3
ENFORCE_EAGER=0
EXL3_FUSED_MOE=1
LANGUAGE_MODEL_ONLY=0
SKIP_MM_PROFILING=1
LIMIT_MM={\"image\":4,\"video\":1}
CHAT_TEMPLATE=/opt/glm53/chat_template.jinja
ABLIT=0
USE_HOST_NCCL=1
READY_TIMEOUT=3600
# MiaAI 2026-08-28 fixes (recipe commits 3605217 / f3043c9 / a099743):
GLM53_SUPPRESS_STOPS_IN_REASONING=1   # thinking-on CoT can restate harness stops; keep stops dormant until </think>
GLM53_MIXED_PREFILL_CHUNK=512        # decode floor: skip mixed sparse-MLA prefill while a peer decodes
VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS=1800  # mid-serve Triton/TileLang JIT can exceed the 300s stock timeout
# Reederey87 kit adoptions 2026-08-29 (vLLM #52805/#53046 backports + W3/W4):
XGRAMMAR_PATCH_HOST=/home/jun/glm53-exl3-recipe/overlay/patch_xgrammar_termination.py
VLLM_PREFIX_CACHE_RETENTION_INTERVAL=0   # W3: sparse KDA retention; cross-session prefix hits 0%->97%+
LONG_PREFILL_TOKEN_THRESHOLD=1792        # W4: long prefills chunk-capped so short reqs are not head-of-line blocked
NEED_GB=95

# rank order: SSH_HOSTS[i] runs rank i (local = forge head rank 0)
SSH_HOSTS=(local 192.168.10.2 192.168.10.3 192.168.10.4)
NODE_IPS=(192.168.10.1 192.168.10.2 192.168.10.3 192.168.10.4)

say() { echo "[glm53-exl3-tp4] $*"; }

remote() {
  local h="$1"; shift
  if [ "$h" = local ]; then bash -c "$*"; else ssh -o BatchMode=yes -o ConnectTimeout=10 "$h" "$*"; fi
}

# ---------------- preflight ----------------
for i in "${!SSH_HOSTS[@]}"; do
  h="${SSH_HOSTS[$i]}"
  say "preflight rank$i ($h)"
  remote "$h" "
    docker rm -f $CONTAINER glm53_sglang glm53-exl3-head glm53-exl3-worker >/dev/null 2>&1 || true
    nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | while read -r p; do [ -n \"\$p\" ] && kill -9 \"\$p\" 2>/dev/null; done || true
    sync; echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true
    avail=\$(grep MemAvailable /proc/meminfo | tr -dc 0-9)
    echo \"  avail mem: \$((avail/1024/1024))GB (need ${NEED_GB}GB)\"
    [ \"\$avail\" -ge $((NEED_GB*1024*1024)) ] || { echo \"  PREFLIGHT FAIL rank$i: mem\"; exit 1; }
    mkdir -p $VLLM_CACHE_HOST
    [ -f $MODEL_HOST/config.json ] || { echo \"  PREFLIGHT FAIL rank$i: weights missing at $MODEL_HOST\"; exit 1; }
  " || { say "preflight FAILED on rank$i ($h)"; exit 1; }
done

# NCCL 2.30.7 staged from the sglang image (pip nvidia-nccl-cu13 2.30.7)
for i in "${!SSH_HOSTS[@]}"; do
  h="${SSH_HOSTS[$i]}"
  remote "$h" "if [ ! -f $NCCL_HOST/$NCCL_SO ]; then
    mkdir -p $NCCL_HOST
    cid=\$(docker create --entrypoint /bin/true glm53-sglang-sm121:dflash 2>/dev/null) || cid=\"\"
    if [ -n \"\$cid\" ]; then
      docker cp \"\$cid\":/opt/sglang/lib/python3.12/site-packages/nvidia/nccl/lib/libnccl.so.2 $NCCL_HOST/$NCCL_SO && docker rm \"\$cid\" >/dev/null
    fi
  fi; ls -la $NCCL_HOST/ | tail -1" | sed "s/^/  rank$i nccl: /"
done

# ---------------- inner serve script (parameterized by NODE_RANK) ----------------
INNER=$(cat << "INNER_EOF"
#!/bin/bash
set -euo pipefail
say() { echo "[glm53-exl3-r${NODE_RANK}] $*"; }

ARGS=(
    --served-model-name "${SERVED_MODEL_NAME}"
    --host 0.0.0.0
    --port "${PORT}"
    --tensor-parallel-size "${TP}"
    --nnodes "${NNODES}"
    --node-rank "${NODE_RANK}"
    --master-addr "${HEAD_IP}"
    --master-port "${MASTER_PORT}"
    --distributed-executor-backend mp
    --tool-call-parser glm47
    --enable-auto-tool-choice
    --reasoning-parser glm45
    --enable-prefix-caching
    --no-enable-flashinfer-autotune
)
[ "${NODE_RANK}" != "0" ] && ARGS+=(--headless)
[ "${ENFORCE_EAGER:-1}" = "1" ] && ARGS+=(--enforce-eager)
[ -n "${QUANTIZATION:-}" ] && [ "${QUANTIZATION}" != "none" ] && ARGS+=(--quantization "${QUANTIZATION}")
[ -n "${MAX_MODEL_LEN:-}" ] && ARGS+=(--max-model-len "${MAX_MODEL_LEN}")
[ -n "${GPU_MEM_UTIL:-}" ] && ARGS+=(--gpu-memory-utilization "${GPU_MEM_UTIL}")
[ -n "${MAX_NUM_SEQS:-}" ] && ARGS+=(--max-num-seqs "${MAX_NUM_SEQS}")
[ -n "${MAX_NUM_BATCHED_TOKENS:-}" ] && ARGS+=(--max-num-batched-tokens "${MAX_NUM_BATCHED_TOKENS}")
[ -n "${LONG_PREFILL_TOKEN_THRESHOLD:-}" ] && ARGS+=(--long-prefill-token-threshold "${LONG_PREFILL_TOKEN_THRESHOLD}")
[ -n "${KV_CACHE_DTYPE:-}" ] && ARGS+=(--kv-cache-dtype "${KV_CACHE_DTYPE}")
if [ "${SPEC_METHOD:-mtp}" = "dflash" ]; then
    ARGS+=(--speculative-config "$(python3 -S -c "import json,os
spec={\"method\":\"dflash\",\"model\":os.environ[\"DFLASH_MODEL_DIR\"],\"num_speculative_tokens\":int(os.environ.get(\"DFLASH_TOKENS\",\"7\")),\"kv_cache_dtype\":\"auto\",\"draft_sample_method\":\"probabilistic\",\"rejection_sample_method\":\"standard\"}
tp=os.environ.get(\"DFLASH_DRAFT_TP\",\"\").strip()
if tp:
    spec[\"draft_tensor_parallel_size\"]=int(tp)
print(json.dumps(spec,separators=(\",\",\":\")))")")
elif [ "${SPEC_METHOD:-}" = "none" ]; then
    :
elif [ "${MTP_TOKENS:-0}" != "0" ]; then
    ARGS+=(--speculative-config "{\"method\":\"mtp\",\"num_speculative_tokens\":${MTP_TOKENS}}")
fi
if [ -n "${CHAT_TEMPLATE:-}" ] && [ -f "${CHAT_TEMPLATE}" ]; then
    ARGS+=(--chat-template "${CHAT_TEMPLATE}")
fi
if [ "${LANGUAGE_MODEL_ONLY:-0}" = "1" ]; then
    ARGS+=(--language-model-only)
else
    [ -n "${LIMIT_MM:-}" ] && ARGS+=(--limit-mm-per-prompt "${LIMIT_MM}")
    [ "${SKIP_MM_PROFILING:-1}" = "1" ] && ARGS+=(--skip-mm-profiling)
fi
if [ -n "${EXTRA_ARGS:-}" ]; then
    EXTRA=(${EXTRA_ARGS})
    ARGS+=("${EXTRA[@]}")
fi

[ -f "${MODEL_DIR}/config.json" ] || { say "FATAL: ${MODEL_DIR}/config.json missing"; ls -la "${MODEL_DIR}" | head; exit 1; }
[ -f /opt/glm53/patch_glm_video_placeholders.py ] && python3 /opt/glm53/patch_glm_video_placeholders.py || true
[ -f /opt/glm53/patch_ablit.py ] && python3 /opt/glm53/patch_ablit.py || true
[ -f /opt/glm53/patch_suppress_stops_in_reasoning.py ] && python3 /opt/glm53/patch_suppress_stops_in_reasoning.py || true
[ -f /opt/glm53/patch_scheduler_decode_floor.py ] && python3 /opt/glm53/patch_scheduler_decode_floor.py || true
[ -f /opt/glm53/patch_hybrid_prefix_hit.py ] && python3 /opt/glm53/patch_hybrid_prefix_hit.py || true
[ -f /opt/glm53/patch_xgrammar_termination.py ] && python3 /opt/glm53/patch_xgrammar_termination.py || true
[ -f /opt/glm53/patch_glm5_drafter_group.py ] && python3 /opt/glm53/patch_glm5_drafter_group.py || true
say "ABLIT=${ABLIT:-0} quant=${QUANTIZATION} spec=${SPEC_METHOD} mmlen=${MAX_MODEL_LEN}"
say "launching: vllm serve ${MODEL_DIR} ${ARGS[*]}"
exec vllm serve "${MODEL_DIR}" "${ARGS[@]}"
INNER_EOF
)

write_inner() {
  local h="$1"
  if [ "$h" = local ]; then
    printf "%s" "$INNER" > /tmp/glm53-exl3-start.sh
    cp /home/jun/glm53-exl3-recipe/overlay/patch_suppress_stops_in_reasoning.py /home/jun/glm53-exl3-recipe/overlay/patch_scheduler_decode_floor.py /home/jun/glm53-exl3-recipe/overlay/patch_hybrid_prefix_hit.py /home/jun/glm53-exl3-recipe/overlay/patch_glm5_drafter_group.py /home/jun/glm53-exl3-recipe/overlay/patch_xgrammar_termination.py /tmp/ 2>/dev/null || true
  else
    printf "%s" "$INNER" | ssh -o BatchMode=yes "$h" "cat > /tmp/glm53-exl3-start.sh"
    scp -q -o BatchMode=yes /home/jun/glm53-exl3-recipe/overlay/patch_suppress_stops_in_reasoning.py /home/jun/glm53-exl3-recipe/overlay/patch_scheduler_decode_floor.py /home/jun/glm53-exl3-recipe/overlay/patch_hybrid_prefix_hit.py /home/jun/glm53-exl3-recipe/overlay/patch_glm5_drafter_group.py /home/jun/glm53-exl3-recipe/overlay/patch_xgrammar_termination.py "$h:/tmp/" 2>/dev/null || true
  fi
}

launch_rank() {
  local rank="$1" h="$2" ip="$3"
  write_inner "$h"
  local nccl_mnt=""
  if [ "$USE_HOST_NCCL" = "1" ]; then nccl_mnt="-v $NCCL_HOST:/nccl:ro -e LD_PRELOAD=/nccl/$NCCL_SO"; fi
  cat > /tmp/glm53-exl3-docker-r$rank.sh << DR_EOF
#!/bin/bash
set -e
docker rm -f $CONTAINER >/dev/null 2>&1 || true
docker run -d --name $CONTAINER \
  --gpus all --network host --ipc=host --shm-size 32g --stop-timeout 60 \
  --device /dev/infiniband --cap-add IPC_LOCK \
  --ulimit memlock=-1 --ulimit stack=67108864 \
  -v $MODEL_HOST:/models/exl3:ro \
  -v $DFLASH_HOST:/models/dflash2:ro \
  -v $VLLM_CACHE_HOST:/root/.cache/vllm \
  -v /tmp/glm53-exl3-start.sh:/start.sh:ro \
  -v /tmp/patch_suppress_stops_in_reasoning.py:/opt/glm53/patch_suppress_stops_in_reasoning.py:ro \
  -v /tmp/patch_scheduler_decode_floor.py:/opt/glm53/patch_scheduler_decode_floor.py:ro \
  -v /tmp/patch_hybrid_prefix_hit.py:/opt/glm53/patch_hybrid_prefix_hit.py:ro \
  -v /tmp/patch_xgrammar_termination.py:/opt/glm53/patch_xgrammar_termination.py:ro \
  -v /tmp/patch_glm5_drafter_group.py:/opt/glm53/patch_glm5_drafter_group.py:ro \
  -v $VLLM_CACHE_HOST/triton:/root/.triton/cache \
  -v $VLLM_CACHE_HOST/tilelang:/root/.tilelang/cache \
  $nccl_mnt \
  -e NODE_RANK=$rank \
  -e SERVED_MODEL_NAME="$SERVED_MODEL_NAME" \
  -e PORT=$PORT -e TP=$TP -e NNODES=$NNODES -e HEAD_IP=$HEAD_IP -e MASTER_PORT=$MASTER_PORT \
  -e QUANTIZATION=$QUANTIZATION -e MAX_MODEL_LEN=$MAX_MODEL_LEN -e GPU_MEM_UTIL=$GPU_MEM_UTIL \
  -e MAX_NUM_SEQS=$MAX_NUM_SEQS -e MAX_NUM_BATCHED_TOKENS=$MAX_NUM_BATCHED_TOKENS \
  -e KV_CACHE_DTYPE=$KV_CACHE_DTYPE -e SPEC_METHOD=$SPEC_METHOD \
  -e DFLASH_TOKENS=$DFLASH_TOKENS -e DFLASH_MODEL_DIR=$DFLASH_MODEL_DIR \
  -e DFLASH_DRAFT_TP=$DFLASH_DRAFT_TP \
  -e LANGUAGE_MODEL_ONLY=$LANGUAGE_MODEL_ONLY -e SKIP_MM_PROFILING=$SKIP_MM_PROFILING \
  -e LIMIT_MM= \
  -e CHAT_TEMPLATE=$CHAT_TEMPLATE -e ENFORCE_EAGER=$ENFORCE_EAGER \
  -e EXL3_FUSED_MOE=$EXL3_FUSED_MOE -e MODEL_DIR=$MODEL_DIR \
  -e ABLIT=$ABLIT -e EXTRA_ARGS="${EXTRA_ARGS:-}" \
  -e VLLM_HOST_IP=$ip \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  -e VLLM_CACHE_ROOT=/root/.cache/vllm \
  -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  -e VLLM_ENGINE_READY_TIMEOUT_S=$READY_TIMEOUT \
  -e VLLM_NO_USAGE_STATS=1 -e DO_NOT_TRACK=1 \
  -e GLM53_SUPPRESS_STOPS_IN_REASONING=$GLM53_SUPPRESS_STOPS_IN_REASONING \
  -e GLM53_MIXED_PREFILL_CHUNK=$GLM53_MIXED_PREFILL_CHUNK \
  -e VLLM_PREFIX_CACHE_RETENTION_INTERVAL=$VLLM_PREFIX_CACHE_RETENTION_INTERVAL \
  -e VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS=$VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS \
  -e NCCL_IB_DISABLE=0 -e NCCL_IB_ROCE_VERSION_NUM=2 -e NCCL_IB_GID_INDEX=-1 \
  -e NCCL_NET=IB -e NCCL_NET_PLUGIN=none -e NCCL_NVLS_ENABLE=0 \
  -e NCCL_CUMEM_ENABLE=0 -e NCCL_IB_MERGE_NICS=0 -e NCCL_CROSS_NIC=0 \
  -e NCCL_IGNORE_CPU_AFFINITY=1 -e NCCL_DEBUG=WARN \
  -e NCCL_SOCKET_IFNAME=enP2p1s0f1np1 -e GLOO_SOCKET_IFNAME=enP2p1s0f1np1 \
  -e NCCL_IB_HCA=roceP2p1s0f1 \
  --entrypoint bash $IMAGE /start.sh
DR_EOF
  if [ "$h" = local ]; then
    bash /tmp/glm53-exl3-docker-r$rank.sh >/dev/null
  else
    cat /tmp/glm53-exl3-docker-r$rank.sh | ssh -o BatchMode=yes "$h" "cat > /tmp/glm53-exl3-docker.sh && bash /tmp/glm53-exl3-docker.sh" >/dev/null
  fi
}

# ---------------- launch: workers (rank 3,2,1) then head (rank 0) ----------------
for rank in 3 2 1; do launch_rank "$rank" "${SSH_HOSTS[$rank]}" "${NODE_IPS[$rank]}"; sleep 8; done
launch_rank 0 local "${NODE_IPS[0]}"

say "launched; ready when: curl -s http://${HEAD_IP}:${PORT}/v1/models"
if [ "${1:-}" != "--no-warmup" ] && [ -f /home/jun/glm53-exl3-recipe/scripts/boot-shape-warmup.sh ]; then
  say "background DFlash2/sampler shape warmup will start once /health is green"
  setsid nohup bash -c "
    for i in \$(seq 1 240); do curl -sf -m 3 http://127.0.0.1:$PORT/health > /dev/null 2>&1 && break; sleep 10; done
    curl -sf -m 3 http://127.0.0.1:$PORT/health > /dev/null 2>&1 || exit 0
    GLM53_WARMUP_MAX_CONCURRENCY=$MAX_NUM_SEQS GLM53_WARMUP_REQ_TIMEOUT=900 GLM53_WARMUP_DFLASH_K=$DFLASH_TOKENS GLM53_WARMUP_TRITON_CACHE_DIR=$VLLM_CACHE_HOST/triton \
      bash /home/jun/glm53-exl3-recipe/scripts/boot-shape-warmup.sh http://127.0.0.1:$PORT $SERVED_MODEL_NAME
  " > /tmp/glm53-exl3-warmup.log 2>&1 < /dev/null &
fi
