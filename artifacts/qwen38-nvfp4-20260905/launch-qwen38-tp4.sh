#!/bin/bash
# launch-qwen38-tp4.sh — nvidia/Qwen3.8-Flash-Next-NVFP4, TP4+EP on 4x DGX Spark (GB10, sm_121)
#
# Shape adapted from our proven GLM TP4 launcher
# (astra-perf-20260905/launcher.snapshot.sh): head-local orchestrator, preflight
# fan-out, host-staged NCCL 2.30.7 LD_PRELOAD, crash-log snapshotting before any
# docker rm, workers-first launch order, per-rank /tmp inner-script mounts.
# Serve flags/lanes adapted from tsw2k/Qwen3.8-Flash-Next-Quad-DGX-Sparks
# (the only published multi-node vLLM recipe for this model on this hardware)
# + getrefined's PLE_FORCE_FP8 resolver + Jun's spec (binding, see
# PREFLIGHT-CHECKLIST.md for the line-by-line mapping).
#
# Run from the artifacts dir ON FORGE (rank 0). Preflight fails loudly rather
# than letting Docker create empty dirs over missing mounts.
#
# Lanes (see report §conflicts before changing):
#   PLE_MODE=mmap (default)     PLE table served from per-node NVMe via mmap
#                               (VLLM_PLE_MMAP=1, workers 32, prewarm on).
#                               KV pool ~5.2M tokens @ GPU_MEM=0.80 (tsw2k-measured).
#   PLE_MODE=resident           stock vocab-sharded table on GPU (~12 GiB/rank at
#                               TP4). Boots at GPU_MEM=0.78. Needed for the
#                               FULL_DECODE_ONLY cudagraph lane.
#   CUDAGRAPH_MODE=piecewise (default)  PIECEWISE + PLE/QSA/GDN splitting ops.
#                               REQUIRED with PLE_MODE=mmap: the mmap gather is a
#                               CPU op + pageable H2D copy and cannot live inside
#                               a captured graph (blazux: "never FULL*").
#   CUDAGRAPH_MODE=full         Jun's spec lane: mode 0 + FULL_DECODE_ONLY, capture
#                               sizes [1,2,4,8] (getrefined-validated shape). Only
#                               valid with PLE_MODE=resident — the launcher refuses
#                               full+mmap unless FORCE_FULL_MMAP=1 (it will die at
#                               capture with "Cannot copy between CPU and CUDA
#                               tensors during CUDA graph capture").
#
# MiaAI merge (2026-09-05, see report): the MTP layer-index alias
# (mtp.layers.0 -> mtp.layers.48) is staged automatically from the checkpoint's
# own config.json + hf_quant_config.json (patched copies bind-mounted over the
# container's config paths; the NVMe copy is never modified), and the image now
# carries the FP8_BLOCK_SCALES MTP-experts patch — together these are what makes
# MTP load at all on the nvidia checkpoint. KV_CACHE_DTYPE=fp8 is an opt-in lane
# (image patch 10, inert at auto). --mm-encoder-tp-mode data adopted (MiaAI-
# verified on this checkpoint+image; vision MLP 4304 % 16 != 0 after TP split).
#
# Env overrides: IMAGE, GPU_MEM (0.80 default; OOM fallback 0.75-0.78), MNBT,
# MTP (2), SEQS (16), MOE_BACKEND (marlin), KV_CACHE_DTYPE (auto; fp8 = opt-in
# lane via image patch 10), ALL2ALL_BACKEND (empty = stock; MiaAI measured
# allgather_reducescatter at TP2+EP — untested at TP4), EXTRA_ARGS, SKIP_PREFLIGHT=1.
set -uo pipefail

IMAGE=${IMAGE:-local/qwen38-gb10:e1}
CONTAINER=qwen38-nvfp4
MODEL_HOST=/home/jun/models/qwen38-flash-next-nvfp4
MODEL_DIR=/models/qwen38
VLLM_CACHE_HOST=/var/tmp/qwen38-vllm-cache
NCCL_HOST="$HOME/nccl-2.30.7"
NCCL_SO=libnccl.so.2.30.7
NCCL_SRC_IMAGE=${NCCL_SRC_IMAGE:-local/glm53-exl3:e2}   # pip nvidia-nccl-cu13 2.30.7 donor

PORT=8000            # GLM owns 18888 — never collide
MASTER_PORT=25100    # GLM uses 25000; keep clear while both live
SERVED_MODEL_NAME=qwen3.8-flash-next
HEAD_IP=192.168.10.1
TP=4
NNODES=4
MAX_MODEL_LEN=262144           # native; 1M YaRN lane exists but is NOT default (vllm#54629 wall)
GPU_MEM_UTIL=${GPU_MEM_UTIL:-0.80}   # OOM fallback: 0.78 / 0.75 (see PREFLIGHT-CHECKLIST)
MAX_NUM_SEQS=${MAX_NUM_SEQS:-16}
# Thinking default (2026-09-05, Eva). The stock chat template treats a missing
# enable_thinking as TRUE with reasoning_effort=xhigh; role bench measured it
# burning the full 16k max_tokens on reasoning and emitting zero content on
# builder tasks (finish_reason=length). Fixed with vLLM's own
# --default-chat-template-kwargs, which feeds BOTH the template renderer and
# the qwen3 reasoning parser (a template-only overlay was tried first: the
# model stopped thinking but the parser still assumed REASONING state and
# filed the answer under message.reasoning — half a fix). Request-level
# chat_template_kwargs.enable_thinking=true still opts in per call.
THINKING_DEFAULT=${THINKING_DEFAULT:-off}   # off|on
MAX_NUM_BATCHED_TOKENS=${MAX_NUM_BATCHED_TOKENS:-8192}  # tsw2k: use 2048 for deep (>32k) prompts
MTP_TOKENS=${MTP_TOKENS:-2}
KV_CACHE_DTYPE=${KV_CACHE_DTYPE:-auto}   # auto = bf16 (default, tsw2k-proven). fp8 = opt-in lane
                                     # (image patch 10, ~1.7x KV pool, quality trade — validate!).
ALL2ALL_BACKEND=${ALL2ALL_BACKEND:-} # empty = stock (tsw2k-proven). allgather_reducescatter = MiaAI TP2 shape.
CFG_STAGE_HOST=/home/jun/qwen38-config-alias   # MTP layer-index alias staging (MiaAI merge)
PLE_MODE=${PLE_MODE:-mmap}     # mmap | resident | offload
CUDAGRAPH_MODE=${CUDAGRAPH_MODE:-piecewise}   # piecewise | full | eager
MOE_BACKEND=${MOE_BACKEND:-marlin}  # marlin = spec fallback lane; stock = tsw2k-proven flashinfer_cutlass (omit flag).
                                    # Set MOE_BACKEND=stock to run the tsw2k-proven path first; marlin if Xid 31.
PLE_MMAP_WORKERS=32            # spec
PLE_MMAP_PREWARM=1            # spec: prewarm the ~48GB table into page cache at boot
NEED_GB=100                   # per-node free RAM floor (tsw2k preflight bar)
READY_TIMEOUT=3600

# rank order: SSH_HOSTS[i] runs rank i (local = forge head, rank 0)
SSH_HOSTS=(local 192.168.10.2 192.168.10.3 192.168.10.4)
NODE_IPS=(192.168.10.1 192.168.10.2 192.168.10.3 192.168.10.4)

# --- fabric (rail B, verified on forge 2026-09-05) ---
IFACE=enP2p1s0f1np1          # 192.168.10.0/24, MTU 9000
IB_HCA=roceP2p1s0f1          # EXACT single-device pin (multi-pair fleets: never
                             # list a port cabled to another cluster)
NCCL_IB_ADDR_RANGE=192.168.10.0/24
NCCL_CROSS_NIC=${NCCL_CROSS_NIC:-1}   # Jun's spec (GLM/tsw2k ran 0; single-rail fabric
                                      # makes this near-moot, spec wins)

# PLE gather + GDN/QSA must run outside CUDA graphs: the splitting-op list
# (blazux, verbatim) for the PIECEWISE lane.
SPLIT='["vllm::unified_attention_with_output","vllm::unified_mla_attention_with_output","vllm::mamba_mixer2","vllm::mamba_mixer","vllm::short_conv","vllm::qwen3_8_flash_next_ple_short_conv","vllm::qwen3_8_flash_next_qsa_with_output","vllm::linear_attention","vllm::qwen_gdn_attention_core","vllm::qwen_gdn_attention_core_fused_norm_packed","vllm::sparse_attn_indexer","vllm::ple_mmap_lookup"]'

say() { echo "[qwen38-tp4] $*"; }

PATCHES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)/patches"

remote() {
  local h="$1"; shift
  if [ "$h" = local ]; then bash -c "$*"; else ssh -o BatchMode=yes -o ConnectTimeout=10 "$h" "$*"; fi
}

# ---------------- lane sanity ----------------
if [ "$CUDAGRAPH_MODE" = "full" ] && [ "$PLE_MODE" = "mmap" ] && [ "${FORCE_FULL_MMAP:-0}" != "1" ]; then
  say "REFUSING: CUDAGRAPH_MODE=full + PLE_MODE=mmap is a known capture failure"
  say "  (the PLE mmap gather is CPU work + pageable H2D; blazux: 'never FULL*')."
  say "  Use CUDAGRAPH_MODE=piecewise (tsw2k-proven), or PLE_MODE=resident for the"
  say "  FULL_DECODE_ONLY lane, or FORCE_FULL_MMAP=1 to try it anyway."
  exit 2
fi
if [ "$PLE_MODE" = "resident" ]; then GPU_MEM_UTIL=${GPU_MEM_UTIL_OVERRIDE:-0.78}; fi
[ "$CUDAGRAPH_MODE" = "full" ] && [ "$PLE_MODE" != "resident" ] && { say "CUDAGRAPH_MODE=full pairs with PLE_MODE=resident"; exit 2; }

# ---------------- preflight ----------------
if [ "${SKIP_PREFLIGHT:-0}" != "1" ]; then
  say "preflight: image $IMAGE, model $MODEL_HOST, port $PORT (GLM owns 18888)"
  for i in "${!SSH_HOSTS[@]}"; do
    h="${SSH_HOSTS[$i]}"
    say "preflight rank$i ($h)"
    remote "$h" "
      set -e
      # crash-log snapshot BEFORE any rm (GLM pattern)
      mkdir -p /home/jun/qwen38-crash-logs
      for c in $CONTAINER; do
        docker inspect \"\$c\" >/dev/null 2>&1 && docker logs --tail 4000 \"\$c\" > /home/jun/qwen38-crash-logs/\$(date +%Y%m%d-%H%M%S)-\$(hostname)-\$c.log 2>&1 || true
      done
      ls -t /home/jun/qwen38-crash-logs/*.log 2>/dev/null | tail -n +21 | xargs -r rm -f
      # GPU + driver
      nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || { echo '  PREFLIGHT FAIL rank$i: nvidia-smi'; exit 1; }
      # co-residency guard: this launcher NEVER kills GPU processes (GLM lives here).
      # A TP4 boot needs the whole node; refuse to start next to another engine.
      apps=\$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | grep -c . || true)
      [ \"\$apps\" = \"0\" ] || { echo \"  PREFLIGHT FAIL rank$i: \$apps GPU compute app(s) already running (GLM up?). Retire/stop it first, or SKIP this check deliberately.\"; exit 1; }
      docker ps --format '{{.Names}}' | grep -qE 'glm53|dspark' && { echo '  PREFLIGHT FAIL rank$i: GLM/dspark container running — take it down (and stop glm-cluster-watch auto-relaunch!) before this lane.'; exit 1; } || true
      docker rm -f $CONTAINER >/dev/null 2>&1 || true
      # memory
      avail=\$(grep MemAvailable /proc/meminfo | tr -dc 0-9)
      echo \"  avail mem: \$((avail/1024/1024))GB (need ${NEED_GB}GB)\"
      [ \"\$avail\" -ge $((NEED_GB*1024*1024)) ] || { echo '  PREFLIGHT FAIL rank$i: mem'; exit 1; }
      swappiness=\$(sysctl -n vm.swappiness 2>/dev/null || echo '?')
      [ \"\$swappiness\" = 0 ] || echo \"  WARN rank$i: vm.swappiness=\$swappiness (tsw2k: >0 can livelock the UVM driver; set 0)\"
      # disk
      free_kb=\$(df --output=avail -k $MODEL_HOST 2>/dev/null | tail -1 | tr -dc 0-9)
      [ -n \"\$free_kb\" ] && [ \"\$free_kb\" -ge 20971520 ] || { echo '  PREFLIGHT FAIL rank$i: <20GB free near model dir'; exit 1; }
      # CX7 rail B: iface, IP, MTU, HCA
      ip -br addr show $IFACE 2>/dev/null | grep -q ${NODE_IPS[$i]}/ || { echo \"  PREFLIGHT FAIL rank$i: $IFACE has no ${NODE_IPS[$i]}\"; exit 1; }
      mtu=\$(cat /sys/class/net/$IFACE/mtu 2>/dev/null)
      [ \"\$mtu\" = 9000 ] || echo \"  WARN rank$i: $IFACE MTU=\$mtu (expect 9000)\"
      ls /sys/class/infiniband/$IB_HCA >/dev/null 2>&1 || { echo \"  PREFLIGHT FAIL rank$i: HCA $IB_HCA missing\"; exit 1; }
      # weights (one NVMe copy per node; PLE table is mmapped from here at runtime)
      test -f $MODEL_HOST/config.json || { echo '  PREFLIGHT FAIL rank$i: weights missing'; exit 1; }
      test -f $MODEL_HOST/model.safetensors.index.json || { echo '  PREFLIGHT FAIL rank$i: index missing'; exit 1; }
      test -f $MODEL_HOST/model-fp8-mtp-ple.safetensors || { echo '  PREFLIGHT FAIL rank$i: PLE/MTP shard file missing'; exit 1; }
      test -f $MODEL_HOST/hf_quant_config.json || echo "  WARN rank$i: no hf_quant_config.json - MTP alias will patch config.json only"
      n=\$(ls $MODEL_HOST/model-*.safetensors 2>/dev/null | wc -l)
      [ \"\$n\" -eq 11 ] || echo \"  WARN rank$i: \$n of 11 safetensors present (download still running?)\"
      # image present (digest/ID equality is checked fleet-wide below)
      docker image inspect $IMAGE >/dev/null 2>&1 || { echo \"  PREFLIGHT FAIL rank$i: image $IMAGE missing (build on forge, fan out per report runbook)\"; exit 1; }
      # drop_caches attempt, sudo-or-skip (spec: drop_caches before loads)
      sync; echo 3 | sudo -n tee /proc/sys/vm/drop_caches >/dev/null 2>&1 || echo '  (drop_caches skipped: no passwordless sudo)'
      mkdir -p $VLLM_CACHE_HOST
      echo '  preflight OK'
    " || { say "preflight FAILED on rank$i ($h)"; exit 1; }
  done

  # image ID must be IDENTICAL on all 4 nodes (GLM/tsw2k lesson: verify the ID,
  # not the tag; four local builds = four divergent images = the failure you
  # cannot diagnose)
  REF_ID=""
  for i in "${!SSH_HOSTS[@]}"; do
    ID=$(remote "${SSH_HOSTS[$i]}" "docker image inspect $IMAGE --format '{{.Id}}' 2>/dev/null" || echo MISSING)
    say "rank$i image: $ID"
    if [ -z "$REF_ID" ]; then REF_ID="$ID"
    elif [ "$ID" != "$REF_ID" ]; then say "PREFLIGHT FAIL: image ID mismatch across ranks"; exit 1; fi
  done
  say "image ID identical on all 4 nodes: $REF_ID"
fi

# ---------------- NCCL 2.30.7 staging ----------------
# Stock image NCCL breaks this fabric (GLM lesson, same hardware); pip 2.30.7 is
# staged per node and LD_PRELOADed. Verified present on forge 2026-09-05.
for i in "${!SSH_HOSTS[@]}"; do
  h="${SSH_HOSTS[$i]}"
  remote "$h" "if [ ! -f $NCCL_HOST/$NCCL_SO ]; then
    mkdir -p $NCCL_HOST
    cid=\$(docker create --entrypoint /bin/true $NCCL_SRC_IMAGE 2>/dev/null) || cid=''
    if [ -n \"\$cid\" ]; then
      docker cp \"\$cid\":/usr/local/lib/python3.12/dist-packages/nvidia/nccl/lib/libnccl.so.2 $NCCL_HOST/$NCCL_SO 2>/dev/null \\
        || docker cp \"\$cid\":/opt/sglang/lib/python3.12/site-packages/nvidia/nccl/lib/libnccl.so.2 $NCCL_HOST/$NCCL_SO
      docker rm \"\$cid\" >/dev/null
    fi
  fi
  if [ ! -f $NCCL_HOST/$NCCL_SO ]; then echo \"rank$i: cannot stage $NCCL_SO (no $NCCL_HOST dir, no donor image) — set NCCL_HOST or stage manually\"; exit 1; fi
  ls -la $NCCL_HOST/$NCCL_SO | tail -1" | sed "s/^/  rank$i nccl: /"
done

# ---------------- MTP layer-index alias staging (MiaAI merge 2026-09-05) ----------------
# vLLM builds the MTP draft layer at the ABSOLUTE index continuing the main stack
# (mtp.layers.48 for num_hidden_layers=48) and matches quantization metadata by
# exact string. The nvidia checkpoint records only mtp.layers.0 (verified
# 2026-09-05 in its config.json + hf_quant_config.json), so the lookup misses and
# the MTP MoE is built unquantized — it dies ~7 min into loading. The alias fix
# (patches/patch_checkpoint_config.py, MiaAI) generates patched config copies ONCE
# on forge, streams them to every node, and bind-mounts them OVER the container's
# config paths. The NVMe copy is never modified.
CFG_MOUNTS=""
rm -rf "$CFG_STAGE_HOST"; mkdir -p "$CFG_STAGE_HOST"
PATCHED=$(python3 "$PATCHES_DIR/patch_checkpoint_config.py" "$MODEL_HOST" "$CFG_STAGE_HOST") || {
  say "FATAL: MTP config alias patch failed on $MODEL_HOST"; exit 1; }
if [ -n "$PATCHED" ]; then
  say "MTP layer-index alias: patched $PATCHED (relative -> absolute MTP layer indices)"
  # MTP expert algo preflight: fail in SECONDS if the dispatch cannot build it
  # (the failure otherwise surfaces ~7 min into the weight load).
  if [ "$MTP_TOKENS" != "0" ]; then
    ALGO=$(python3 "$PATCHES_DIR/patch_checkpoint_config.py" --mtp-moe-algo "$MODEL_HOST") && ARC=0 || ARC=$?
    if [ "$ARC" = "3" ]; then
      say "REFUSING: MTP experts are ${ALGO}, which the image's mixed-precision MoE"
      say "  dispatch cannot build. Set MTP_TOKENS=0 to serve without speculative"
      say "  decoding (tsw2k fallback lane), or extend image patch 9."
      exit 2
    fi
    say "MTP experts quantization: ${ALGO:-unquantized} (buildable with image patch 9)"
  fi
  # normalize staged names to the plain baselines the container expects
  [ -f "$CFG_STAGE_HOST/config_patched.json" ] && cp "$CFG_STAGE_HOST/config_patched.json" "$CFG_STAGE_HOST/config.json"
  [ -f "$CFG_STAGE_HOST/hf_quant_config_patched.json" ] && cp "$CFG_STAGE_HOST/hf_quant_config_patched.json" "$CFG_STAGE_HOST/hf_quant_config.json"
  CFG_MOUNTS="-v $CFG_STAGE_HOST/config.json:$MODEL_DIR/config.json:ro"
  [ -f "$CFG_STAGE_HOST/hf_quant_config.json" ] && CFG_MOUNTS="$CFG_MOUNTS -v $CFG_STAGE_HOST/hf_quant_config.json:$MODEL_DIR/hf_quant_config.json:ro"
  # stream to every worker node (forge is rank 0/local and uses the stage dir directly)
  for i in "${!SSH_HOSTS[@]}"; do
    h="${SSH_HOSTS[$i]}"; [ "$h" = local ] && continue
    for f in config.json hf_quant_config.json; do
      [ -f "$CFG_STAGE_HOST/$f" ] || continue
      cat "$CFG_STAGE_HOST/$f" | ssh -o BatchMode=yes "$h" "mkdir -p $CFG_STAGE_HOST && cat > $CFG_STAGE_HOST/$f"
    done
  done
  say "config alias staged on all nodes: $CFG_STAGE_HOST (bind-mounted over $MODEL_DIR/*.json)"
else
  say "MTP layer-index alias: checkpoint already declares absolute MTP indices (no overlay)"
fi

# ---------------- inner serve script (parameterized by NODE_RANK) ----------------
INNER=$(cat << "INNER_EOF"
#!/bin/bash
set -euo pipefail
say() { echo "[qwen38-r${NODE_RANK}] $*"; }

ARGS=(
    "${MODEL_DIR}"
    --served-model-name "${SERVED_MODEL_NAME}"
    --host 0.0.0.0
    --port "${PORT}"
    --tensor-parallel-size "${TP}"
    --enable-expert-parallel        # MANDATORY at TP4: plain TP shards MoE intermediate
                                    # 640->160/rank and NVFP4 CUTLASS dies on padding
    --nnodes "${NNODES}"
    --node-rank "${NODE_RANK}"
    --master-addr "${HEAD_IP}"
    --master-port "${MASTER_PORT}"
    --distributed-executor-backend mp
    --load-format safetensors
    --max-model-len "${MAX_MODEL_LEN}"
    --max-num-seqs "${MAX_NUM_SEQS}"
    --max-num-batched-tokens "${MAX_NUM_BATCHED_TOKENS}"
    --gpu-memory-utilization "${GPU_MEM_UTIL}"
    --kv-cache-dtype "${KV_CACHE_DTYPE}"
    --enable-chunked-prefill
    --enable-prefix-caching          # correct with this image's block_size fix
    --mm-encoder-tp-mode data        # MiaAI-verified on this checkpoint+image: the
                                     # vision MLP intermediate 4304 is not %16 after
                                     # TP split (2152@TP2, 1076@TP4); data mode
                                     # replicates the encoder per rank instead of
                                     # sharding it into a load-time crash
    --enable-auto-tool-choice --tool-call-parser qwen3_coder
    --reasoning-parser qwen3
    --no-enable-flashinfer-autotune
)
# EP all2all algorithm: stock by default (tsw2k-proven at TP4). MiaAI measured
# allgather_reducescatter at TP2+EP on the same image — opt-in via ALL2ALL_BACKEND.
if [ -n "${ALL2ALL_BACKEND:-}" ]; then
    ARGS+=(--all2all-backend "${ALL2ALL_BACKEND}")
fi
[ "${NODE_RANK}" != "0" ] && ARGS+=(--headless)

# cudagraph lane
case "${CUDAGRAPH_MODE}" in
  piecewise)
    ARGS+=(-cc.cudagraph_mode=PIECEWISE -cc.splitting_ops="${SPLIT_OPS}") ;;
  full)
    # Jun's spec lane: FULL_DECODE_ONLY, sizes [1,2,4,8] (getrefined-validated
    # shape). Resident-PLE only — see launcher header.
    ARGS+=(--compilation-config "{\"mode\":0,\"cudagraph_mode\":\"FULL_DECODE_ONLY\",\"cudagraph_capture_sizes\":[1,2,4,8]}") ;;
  eager)
    ARGS+=(--enforce-eager) ;;
esac

# MTP speculative decoding, k=2 (spec; tsw2k measured 0.856 acceptance at k=2)
if [ "${MTP_TOKENS:-0}" != "0" ]; then
    ARGS+=(--speculative-config "{\"method\":\"mtp\",\"num_speculative_tokens\":${MTP_TOKENS}}")
fi

# FlashInfer CUTLASS Xid 31 on sm121 -> marlin MoE backend (Jun's spec; EP keeps
# experts whole either way). Env-clear to fall back to stock EP kernels.
if [ -n "${MOE_BACKEND:-}" ] && [ "${MOE_BACKEND}" != "stock" ]; then
    ARGS+=(--moe-backend "${MOE_BACKEND}")
fi

# Thinking default OFF at the serving layer (see THINKING_DEFAULT in the outer
# launcher). One array element so the JSON is never word-split.
if [ "${THINKING_DEFAULT:-off}" = "off" ]; then
    ARGS+=(--default-chat-template-kwargs '{"enable_thinking": false}')
fi

if [ -n "${EXTRA_ARGS:-}" ]; then
    EXTRA=(${EXTRA_ARGS})
    ARGS+=("${EXTRA[@]}")
fi

[ -f "${MODEL_DIR}/config.json" ] || { say "FATAL: ${MODEL_DIR}/config.json missing"; ls -la "${MODEL_DIR}" | head; exit 1; }
say "ple=${PLE_MODE} graphs=${CUDAGRAPH_MODE} k=${MTP_TOKENS:-0} mmbtu=${GPU_MEM_UTIL} mnbt=${MAX_NUM_BATCHED_TOKENS} seqs=${MAX_NUM_SEQS} moe=${MOE_BACKEND:-stock}"
say "launching: vllm serve ${ARGS[*]}"
exec vllm serve "${ARGS[@]}"
INNER_EOF
)

write_inner() {
  local h="$1"
  if [ "$h" = local ]; then
    printf "%s" "$INNER" > /tmp/qwen38-start.sh
  else
    printf "%s" "$INNER" | ssh -o BatchMode=yes "$h" "cat > /tmp/qwen38-start.sh"
  fi
}

launch_rank() {
  local rank="$1" h="$2" ip="$3"
  write_inner "$h"
  local nccl_mnt="-v $NCCL_HOST:/nccl:ro -e LD_PRELOAD=/nccl/$NCCL_SO"
  local ple_env=""
  case "$PLE_MODE" in
    mmap)     ple_env="-e VLLM_PLE_MMAP=1 -e VLLM_PLE_MMAP_WORKERS=$PLE_MMAP_WORKERS -e VLLM_PLE_MMAP_PREWARM=$PLE_MMAP_PREWARM" ;;
    resident) ple_env="" ;;   # stock vocab-sharded table (~12GiB/rank at TP4); PLE_FORCE_FP8 below opens it
    offload)  ple_env="-e VLLM_PLE_CPU_OFFLOAD=1" ;;
  esac
  local ple_caps=""
  [ "$PLE_MODE" = "offload" ] && ple_caps="--cap-add SYS_PTRACE"
  cat > /tmp/qwen38-docker-r$rank.sh << DR_EOF
#!/bin/bash
set -e
docker rm -f $CONTAINER >/dev/null 2>&1 || true
docker run -d --name $CONTAINER --restart no \
  --log-driver json-file --log-opt max-size=25m --log-opt max-file=4 \
  --gpus all --network host --ipc host --shm-size 32g --stop-timeout 60 \
  --memory 112g --memory-swap 112g \
  --device /dev/infiniband --cap-add IPC_LOCK --cap-add SYS_NICE $ple_caps \
  --ulimit memlock=-1 --ulimit stack=67108864 \
  --ulimit nofile=1048576:1048576 \
  -v $MODEL_HOST:$MODEL_DIR:ro \
  $CFG_MOUNTS \
  -v $VLLM_CACHE_HOST:/root/.cache/vllm \
  -v $VLLM_CACHE_HOST:/root/.cache/vllm \
  -v $VLLM_CACHE_HOST/triton:/root/.triton/cache \
  -v /tmp/qwen38-start.sh:/start.sh:ro \
  $nccl_mnt \
  -e NODE_RANK=$rank \
  -e MODEL_DIR=$MODEL_DIR -e SERVED_MODEL_NAME="$SERVED_MODEL_NAME" \
  -e PORT=$PORT -e TP=$TP -e NNODES=$NNODES -e HEAD_IP=$HEAD_IP -e MASTER_PORT=$MASTER_PORT \
  -e MAX_MODEL_LEN=$MAX_MODEL_LEN -e GPU_MEM_UTIL=$GPU_MEM_UTIL \
  -e MAX_NUM_SEQS=$MAX_NUM_SEQS -e MAX_NUM_BATCHED_TOKENS=$MAX_NUM_BATCHED_TOKENS \
  -e KV_CACHE_DTYPE=$KV_CACHE_DTYPE -e MTP_TOKENS=$MTP_TOKENS \
  -e THINKING_DEFAULT=$THINKING_DEFAULT \
  -e CUDAGRAPH_MODE=$CUDAGRAPH_MODE -e MOE_BACKEND="${MOE_BACKEND}" \
  -e PLE_MODE=$PLE_MODE \
  -e SPLIT_OPS=${SPLIT@Q} \
  -e EXTRA_ARGS="${EXTRA_ARGS:-}" \
  -e VLLM_HOST_IP=$ip \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  -e VLLM_CACHE_ROOT=/root/.cache/vllm \
  -e VLLM_ENGINE_READY_TIMEOUT_S=$READY_TIMEOUT \
  -e VLLM_NO_USAGE_STATS=1 -e DO_NOT_TRACK=1 \
  -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  -e VLLM_ALLOW_LONG_MAX_MODEL_LEN=0 \
  -e PLE_FORCE_FP8=1 \
  -e VLLM_QSA_DET_TOPK=1 -e VLLM_QSA_DET_LIB=/opt/llm/kernel-det/_C_det.so \
  -e VLLM_QSA_EXACT_TOPK=${VLLM_QSA_EXACT_TOPK:-0} \
  -e VLLM_USE_FLASHINFER_SAMPLER=1 \
  -e TORCH_CUDA_ARCH_LIST=12.1f -e CUTE_DSL_ARCH=sm_121a -e FLASHINFER_CUDA_ARCH_LIST=12.1a \
  $ple_env \
  -e NCCL_NET=IB -e NCCL_IB_DISABLE=0 \
  -e NCCL_IB_ROCE_VERSION_NUM=2 -e NCCL_IB_ADDR_FAMILY=AF_INET \
  -e NCCL_IB_ADDR_RANGE=$NCCL_IB_ADDR_RANGE \
  -e NCCL_IB_HCA=$IB_HCA \
  -e NCCL_SOCKET_IFNAME=$IFACE -e GLOO_SOCKET_IFNAME=$IFACE -e TP_SOCKET_IFNAME=$IFACE \
  -e NCCL_CROSS_NIC=$NCCL_CROSS_NIC \
  -e NCCL_NVLS_ENABLE=0 -e NCCL_IB_MERGE_NICS=0 -e NCCL_CUMEM_ENABLE=0 \
  -e NCCL_IGNORE_CPU_AFFINITY=1 -e NCCL_DEBUG=WARN \
  -e TORCH_NCCL_ASYNC_ERROR_HANDLING=1 \
  --entrypoint bash $IMAGE /start.sh
DR_EOF
  if [ "$h" = local ]; then
    bash /tmp/qwen38-docker-r$rank.sh >/dev/null
  else
    cat /tmp/qwen38-docker-r$rank.sh | ssh -o BatchMode=yes "$h" "cat > /tmp/qwen38-docker.sh && bash /tmp/qwen38-docker.sh" >/dev/null
  fi
  remote "$h" "sleep 2; docker ps --format '{{.Names}}' | grep -x '$CONTAINER' || { docker logs --tail 100 $CONTAINER 2>&1; echo 'RANK $rank EXITED — capture logs BEFORE any docker rm'; exit 1; }" || { say "rank$rank container exited at startup"; exit 1; }
  say "rank$rank up ($h)"
}

# ---------------- launch: workers (3,2,1) then head (0), 15s apart ----------------
for rank in 3 2 1; do
  launch_rank "$rank" "${SSH_HOSTS[$rank]}" "${NODE_IPS[$rank]}"
  sleep 15
done
launch_rank 0 local "${NODE_IPS[0]}"

say "launched. ready when: curl -s http://${HEAD_IP}:${PORT}/v1/models"
say "NOTE: this vLLM build returns thinking in message.reasoning (not reasoning_content)"
if [ "${1:-}" = "--wait" ]; then
  for i in $(seq 1 $((READY_TIMEOUT/30))); do
    curl -sf -m 5 "http://${HEAD_IP}:${PORT}/v1/models" >/dev/null 2>&1 && { say "READY after ~$((i*30))s"; exit 0; }
    sleep 30
  done
  say "TIMEOUT after ${READY_TIMEOUT}s — check: ssh <rank> docker logs --tail 200 $CONTAINER"
  exit 1
fi
