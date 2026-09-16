#!/usr/bin/env bash
# unc-trial.sh — abliterated DSV4.1-Flash on the SGLang TP4 world, gated, auto-revert.
# Steps: profile swap → stop → share → pack(engram-unc, once) → serve → gates → keep|revert.
# Uncensored is NOT the serving brain unless every gate passes (Jun, 2026-09-13 rule).
set -uo pipefail
T=/home/jun/dsv41-sglang-trial-20260914; KIT=$T/mia; OUT=$T/gates-unc; mkdir -p "$OUT"
API=http://127.0.0.1:8000; MODEL=deepseek-v4.1-flash
UNC=/home/jun/models/deepseek-v4.1-flash-uncensored-fp8
LOG=$OUT/trial.log
say(){ echo "[$(date -Is)] $*" | tee -a "$LOG"; }
cd "$KIT"

# 0. profiles
[[ -f .env.tp4.censored ]] || cp .env.tp4 .env.tp4.censored
if [[ ! -f .env.tp4.uncensored ]]; then
  sed -e "s|^MODEL_DIR=.*|MODEL_DIR=$UNC|" -e "s|^COMMON_MODEL=.*|COMMON_MODEL=$UNC|" \
      -e "s|^ENGRAM_DIR=.*|ENGRAM_DIR=\$HOME/dsv41-engram-unc|" .env.tp4.censored > .env.tp4.uncensored
  echo "WORKER_ENGRAM_DIR=/home/jun/dsv41-4x-spark/engram-unc" >> .env.tp4.uncensored
fi
grep -qE "^MODEL_DIR=$UNC" .env.tp4.uncensored || { say "FATAL: uncensored profile malformed"; exit 2; }

revert(){
  say "REVERT: restoring censored profile and serving it"
  cp .env.tp4.censored .env.tp4
  ./stop.sh >>"$LOG" 2>&1; sleep 5
  timeout 2400 $T/recover-sglang.sh >>"$LOG" 2>&1 || true
  pkill -f "start.sh serve" 2>/dev/null || true
  curl -fsS --max-time 300 -H "Content-Type: application/json" -X POST $API/v1/chat/completions -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":1}" >/dev/null 2>&1 \
    && say "REVERT: censored world back" || say "REVERT FAILED — manual attention"
}

# 1. stop + swap
say "trial start: stopping censored world"
./stop.sh >>"$LOG" 2>&1; sleep 5
cp .env.tp4.uncensored .env.tp4

# 2. weights on workers: LOCAL bind volume (checkpoint is sha256-identical on every node).
# The NFS exporter is untouched: it cannot be swapped live (kernel nfsd state makes the
# container unkillable while it holds exports; run 2 died on exactly that).
say "weights: verifying local bind volume dsv41-weights-unc on all workers"
for h in anvil ember flame; do
  ssh -o BatchMode=yes $h "docker volume inspect dsv41-weights-unc >/dev/null 2>&1 || docker volume create --driver local --opt type=none --opt o=bind --opt device=$UNC dsv41-weights-unc >/dev/null; docker run --rm -v dsv41-weights-unc:/m:ro alpine test -f /m/config.json" >>"$LOG" 2>&1 \
    || { say "weights FAILED: $h local volume unusable"; revert; exit 5; }
done
say "weights: all workers mount the uncensored checkpoint locally"
need_pack=0
[[ -n "$(ls $HOME/dsv41-engram-unc 2>/dev/null)" ]] || need_pack=1
for h in anvil ember flame; do ssh -o BatchMode=yes $h "ls /home/jun/dsv41-4x-spark/engram-unc 2>/dev/null | grep -q ." || need_pack=1; done
if [[ $need_pack -eq 1 ]]; then
  say "pack: Engram shards → engram-unc on all 4 nodes (world is stopped; bulk NVMe writes are safe now)"
  ./start-tp4.sh pack >>"$LOG" 2>&1 || { say "pack FAILED"; revert; exit 3; }
else say "pack: engram-unc already present on all nodes, skipping"; fi

# 3. serve
say "serve: booting uncensored world"
# serve directly: NFS_SHARE=0 in the unc profile, so start-tp4.sh skips cmd_share (which would
# touch the live censored exporter). Memory drain first, same as recover does.
for i in $(seq 1 24); do apps=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | wc -l); [ "${apps:-1}" = "0" ] && break; sleep 5; done
timeout 2400 ./start-tp4.sh serve >>"$LOG" 2>&1 || say "start-tp4.sh serve returned non-zero/timeout — verifying health independently"
ok=0; for i in $(seq 1 30); do curl -fsS --max-time 120 -H "Content-Type: application/json" -X POST $API/v1/chat/completions -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":1}" >/dev/null 2>&1 && { ok=1; break; }; sleep 20; done
[[ $ok -eq 1 ]] || { say "serve FAILED: no completion after recover"; revert; exit 4; }
pkill -f "start.sh serve" 2>/dev/null || true
timeout 900 python3 /home/jun/dsv41-vllm/ops/prewarm.py $API/v1 $MODEL >>"$LOG" 2>&1 || true
say "serve: up. running gates"

# 4. gates
pass=1
cd $T/gates
for i in 1 2 3; do
  sudo docker cp rawgen3.py dsv41-head:/tmp/rawgen3.py >/dev/null 2>&1
  sudo docker exec dsv41-head python3 /tmp/rawgen3.py > "$OUT/g0-run$i.txt" 2>&1
  if grep -q "RAW OUTPUT" "$OUT/g0-run$i.txt" && grep -A3 "RAW OUTPUT" "$OUT/g0-run$i.txt" | grep -qiE "42"; then say "G0 run$i PASS"; else say "G0 run$i FAIL"; pass=0; fi
done
python3 v41gate.py $API/v1 $MODEL > "$OUT/g1-garble.log" 2>&1
g1=$(tail -1 "$OUT/g1-garble.log"); say "G1: $g1"; echo "$g1" | grep -q "30/30 clean" || pass=0
API=$API MODEL=$MODEL bash gates-tool.sh g2 > "$OUT/g2-tool.log" 2>&1; g2=$(tail -1 "$OUT/g2-tool.log"); say "G2: $g2"; grep -q "TOOL_ROUNDTRIP 3/3" "$OUT/g2-tool.log" || pass=0
API=$API MODEL=$MODEL bash gates-tool.sh g3 > "$OUT/g3-reasoning.log" 2>&1; g3=$(tail -1 "$OUT/g3-reasoning.log"); say "G3: $g3"; grep -q "REASONING_PARSER PASS" "$OUT/g3-reasoning.log" || pass=0
python3 v41needle.py --base $API/v1 --model $MODEL --targets 32000,400000 --out "$OUT/g4-needle.json" > "$OUT/g4-needle.log" 2>&1
grep -o "{\"target\"[^}]*}" "$OUT/g4-needle.log" | tee -a "$LOG"
n_pass=$(grep -o "\"pass\": true" "$OUT/g4-needle.log" | wc -l); say "G4 needle: $n_pass/2 pass"; [[ $n_pass -eq 2 ]] || pass=0

# 5. verdict
if [[ $pass -eq 1 ]]; then
  say "VERDICT: ALL GATES PASS — uncensored world left SERVING (Jun decides whether it stays). Revert: cp .env.tp4.censored .env.tp4 && restart."
  echo PASS > "$OUT/VERDICT"
else
  say "VERDICT: GATE FAILURE — reverting to censored per rule"
  echo FAIL > "$OUT/VERDICT"; revert
fi
say "trial done"
