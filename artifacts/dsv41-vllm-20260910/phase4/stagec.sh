#!/bin/bash
# Stage C combo verification A/B/A at 420k.
# A = original baseline (probabilistic draft, MAX_BATCHED=8192); B = champion (greedy, 16384).
# Each leg: relaunch -> shortbench 3 reps. B leg also runs the final tables.
set -u
cd /home/jun
R=/home/jun/dsv41-vllm/phase4
log(){ echo "[stageC] $*"; }

launch_env(){
  local label="$1"; shift
  set -a; source /home/jun/dsv41-vllm/CHAMPION.env; set +a
  for kv in "$@"; do export "$kv"; done
  log "launch $label: DRAFT_METHOD=$DRAFT_METHOD MAX_BATCHED=$MAX_BATCHED"
  bash /home/jun/launch-dsv41-vllm-tp4.sh > /home/jun/dsv41-vllm/logs/boot420k-$label.log 2>&1
  log "$label launcher exit=$?"
}

# ---- A1: baseline ----
launch_env combo-a1 DRAFT_METHOD=probabilistic MAX_BATCHED=8192
bash $R/shortbench.sh combo-a1 3 > $R/shortbench-combo-a1.log 2>&1
log "A1 bench exit=$?"
python3 $R/armmetrics.py $R/combo-a1 > $R/combo-a1-metrics.json 2>&1

# ---- B: champion + final tables ----
set -a; source /home/jun/dsv41-vllm/CHAMPION.env; set +a
log "launch combo-b: DRAFT_METHOD=$DRAFT_METHOD MAX_BATCHED=$MAX_BATCHED"
bash /home/jun/launch-dsv41-vllm-tp4.sh > /home/jun/dsv41-vllm/logs/boot420k-combo-b.log 2>&1
log "B launcher exit=$?"
bash $R/shortbench.sh combo-b 3 > $R/shortbench-combo-b.log 2>&1
log "B shortbench exit=$?"
python3 $R/armmetrics.py $R/combo-b > $R/combo-b-metrics.json 2>&1
bash $R/finalbench.sh > $R/finalbench.log 2>&1
log "finalbench exit=$?"

# ---- A2: baseline again ----
launch_env combo-a2 DRAFT_METHOD=probabilistic MAX_BATCHED=8192
bash $R/shortbench.sh combo-a2 3 > $R/shortbench-combo-a2.log 2>&1
log "A2 bench exit=$?"
python3 $R/armmetrics.py $R/combo-a2 > $R/combo-a2-metrics.json 2>&1

# ---- leave the champion running (armed) ----
set -a; source /home/jun/dsv41-vllm/CHAMPION.env; set +a
log "relaunching champion to leave the cluster in the shipped config"
bash /home/jun/launch-dsv41-vllm-tp4.sh > /home/jun/dsv41-vllm/logs/boot420k-final-champion.log 2>&1
log "final champion launcher exit=$?"
log "STAGEC DONE"
