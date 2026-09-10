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
[ "${ASYNC_SCHEDULING:-0}" = "1" ] && ARGS+=(--async-scheduling)
# 2026-09-03: rolling per-request logs. Each request logs its id, prompt length
# and sampling params (prompt text truncated to MAX_LOG_LEN chars). Pair with
# docker json-file rotation below so this never fills the disk.
[ "${LOG_REQUESTS:-1}" = "1" ] && ARGS+=(--enable-log-requests --max-log-len "${MAX_LOG_LEN:-200}")
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
# C4-sweep toggles (2026-09-03): SKIP_PATCHES="patch_a.py patch_b.py" skips named patches.
apply_patch() { local p="$1" b; b=$(basename "$p"); case " ${SKIP_PATCHES:-} " in *" $b "*) echo "[patch] SKIPPED $b (SKIP_PATCHES)"; return 0;; esac; [ -f "$p" ] && python3 "$p" || true; }
apply_patch /opt/glm53/patch_glm_video_placeholders.py
apply_patch /opt/glm53/patch_ablit.py
apply_patch /opt/glm53/patch_suppress_stops_in_reasoning.py
apply_patch /opt/glm53/patch_scheduler_decode_floor.py
apply_patch /opt/glm53/patch_hybrid_prefix_hit.py
apply_patch /opt/glm53/patch_xgrammar_termination.py
apply_patch /opt/glm53/patch_glm5_drafter_group.py
apply_patch /opt/glm53/patch_spinwait.py
apply_patch /opt/glm53/patch_indexer_workspace.py
apply_patch /opt/glm53/patch_exl3_fat_kernel.py
apply_patch /opt/glm53/patch_kpool_tail_slotmap.py
say "async=${ASYNC_SCHEDULING:-0} k=${DFLASH_TOKENS} small_ok=${GLM53_MIXED_PREFILL_SMALL_OK:-0} ABLIT=${ABLIT:-0} quant=${QUANTIZATION} spec=${SPEC_METHOD} mmlen=${MAX_MODEL_LEN} mnbt=${MAX_NUM_BATCHED_TOKENS} fat=${EXL3_FAT_KERNEL:-0}"
say "launching: vllm serve ${MODEL_DIR} ${ARGS[*]}"
exec vllm serve "${MODEL_DIR}" "${ARGS[@]}"