#!/bin/bash
# run-arm.sh <label> [VAR=value ...] — relaunch champion+overrides, shortbench 3 reps, extract metrics.
set -u
LABEL=$1; shift
cd /home/jun
set -a; source /home/jun/dsv41-vllm/CHAMPION.env; set +a
for kv in "$@"; do export "$kv"; done
echo "[arm $LABEL] env: MAXLEN=$MAXLEN GMU=$GMU SEQS=$SEQS SPEC_K=$SPEC_K DRAFT_METHOD=$DRAFT_METHOD ENGRAM_THREADS=$ENGRAM_THREADS MAX_BATCHED=$MAX_BATCHED EXTRA_ENV_ARGS=${EXTRA_ENV_ARGS:-} VLLM_EXTRA=${VLLM_EXTRA:-}"
bash /home/jun/launch-dsv41-vllm-tp4.sh > /home/jun/dsv41-vllm/logs/boot420k-$LABEL.log 2>&1
echo "[arm $LABEL] launcher exit=$?"
bash /home/jun/dsv41-vllm/phase4/shortbench.sh "$LABEL" 3 > /home/jun/dsv41-vllm/phase4/shortbench-$LABEL.log 2>&1
echo "[arm $LABEL] bench exit=$?"
python3 /home/jun/dsv41-vllm/phase4/armmetrics.py /home/jun/dsv41-vllm/phase4/$LABEL > /home/jun/dsv41-vllm/phase4/$LABEL-metrics.json 2>&1
echo "[arm $LABEL] DONE"
