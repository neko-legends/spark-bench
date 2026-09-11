#!/bin/bash
# Phase-4b world-down window: clean gpuflip + NCCL variant pre-screen.
# Run ON FORGE with the world already stopped. Leaves GPUs free; does NOT relaunch.
set -u
LVL=/home/jun/dsv41-vllm
OUT=$LVL/phase4/gpuflip-postreboot
NCCLOUT=$LVL/phase4/nccl-prescreen
mkdir -p "$OUT" "$NCCLOUT"
IMG=vllm-dsv41:overlay5
IFACE=enP2p1s0f1np1
HCA=roceP2p1s0f1
RANGE=192.168.10.0/24
NODES="forge:local:192.168.10.1 anvil:192.168.10.2:192.168.10.2 ember:192.168.10.3:192.168.10.3 flame:192.168.10.4:192.168.10.4"

say(){ echo "[window] $*"; }

# ---- clean gpuflip on all 4 (GPUs must be free) ----
say "clean gpuflip on all 4 nodes"
run_flip(){
  local name="$1" h="$2"
  if [ "$h" = local ]; then
    bash -s > /tmp/gpuflip-$name.raw 2>&1 <<'EOF'
set -e
mkdir -p /tmp/lvr
cp /home/jun/dsv41-vllm/tony/tools/gpuflip.py /tmp/lvr/gpuflip.py
( timeout 115 nvidia-smi --query-gpu=clocks.sm,power.draw --format=csv,noheader,nounits -lms 200 </dev/null | while read -r l; do echo "N $(date +%s.%N) $l"; done > /tmp/lvr/smi10.txt ) &
docker run --rm --gpus all --network none --memory 8g -v /tmp/lvr:/w --entrypoint timeout vllm-dsv41:overlay5 150 python3 /w/gpuflip.py > /tmp/lvr/flip10.txt 2>&1
wait
cat /tmp/lvr/flip10.txt /tmp/lvr/smi10.txt
EOF
  else
    ssh -o BatchMode=yes "$h" 'set -e
mkdir -p /tmp/lvr
cp /home/jun/dsv41-vllm/tony/tools/gpuflip.py /tmp/lvr/gpuflip.py
( timeout 115 nvidia-smi --query-gpu=clocks.sm,power.draw --format=csv,noheader,nounits -lms 200 </dev/null | while read -r l; do echo "N $(date +%s.%N) $l"; done > /tmp/lvr/smi10.txt ) &
docker run --rm --gpus all --network none --memory 8g -v /tmp/lvr:/w --entrypoint timeout vllm-dsv41:overlay5 150 python3 /w/gpuflip.py > /tmp/lvr/flip10.txt 2>&1
wait
cat /tmp/lvr/flip10.txt /tmp/lvr/smi10.txt' > /tmp/gpuflip-$name.raw 2>&1
  fi
}
for spec in $NODES; do
  n=${spec%%:*}; rest=${spec#*:}; h=${rest%%:*}
  run_flip "$n" "$h" &
done
wait
for n in forge anvil ember flame; do cp /tmp/gpuflip-$n.raw "$OUT/flip-$n.txt"; done
python3 $LVL/tony/tools/flipsum.py "$OUT" > "$OUT/flip-summary.txt" 2>&1
cat "$OUT/flip-summary.txt"

# ---- NCCL variant pre-screen ----
NENV="-e NCCL_NET=IB -e NCCL_IB_DISABLE=0 -e NCCL_IB_HCA=$HCA -e NCCL_IB_GID_INDEX=auto \
 -e NCCL_IB_ROCE_VERSION_NUM=2 -e NCCL_IB_ADDR_FAMILY=AF_INET -e NCCL_IB_ADDR_RANGE=$RANGE \
 -e NCCL_SOCKET_IFNAME=$IFACE -e GLOO_SOCKET_IFNAME=$IFACE \
 -e NCCL_NVLS_ENABLE=0 -e NCCL_CROSS_NIC=1 -e NCCL_IB_MERGE_NICS=0 -e NCCL_CUMEM_ENABLE=0 \
 -e NCCL_IGNORE_CPU_AFFINITY=1 -e MASTER_ADDR=192.168.10.1 -e MASTER_PORT=29610 -e WORLD_SIZE=4"

run_variant(){
  local label="$1" extra="$2"
  local d="$NCCLOUT/$label"; mkdir -p "$d"
  say "nccl variant $label ($extra)"
  for spec in $NODES; do
    n=${spec%%:*}; rest=${spec#*:}; h=${rest%%:*}; r=""
    case $n in forge) r=0;; anvil) r=1;; ember) r=2;; flame) r=3;; esac
    local cmd="docker run --rm --gpus all --network host --ipc host --memory 8g --ulimit memlock=-1:-1 --cap-add IPC_LOCK \
 --device /dev/infiniband:/dev/infiniband $NENV $extra -e RANK=$r -e NODE=$n -v /tmp/lvr:/w --entrypoint timeout $IMG 240 python3 /w/nccl_lat.py"
    if [ "$h" = local ]; then bash -c "$cmd" > "$d/nccl-$n.txt" 2>&1 &
    else ssh -o BatchMode=yes "$h" "$cmd" > "$d/nccl-$n.txt" 2>&1 & fi
  done
  wait
  # seed /tmp/lvr/nccl_lat.py on all nodes first time
  {
    grep -hE " r[0-3] " "$d"/nccl-forge.txt | head -12
    for n in anvil ember flame; do grep -hE " r[0-3] " "$d/nccl-$n.txt" | grep -v "NCCL INFO" | tail -2; done
  } | tee "$d/summary.txt"
}

# stage nccl_lat.py + gpuflip.py on all nodes
for spec in $NODES; do
  n=${spec%%:*}; rest=${spec#*:}; h=${rest%%:*}
  if [ "$h" = local ]; then cp $LVL/tony/tools/nccl_lat.py /tmp/lvr/; else ssh -o BatchMode=yes "$h" "mkdir -p /tmp/lvr; cat > /tmp/lvr/nccl_lat.py" < $LVL/tony/tools/nccl_lat.py; fi
done

run_variant baseline ""
run_variant algo_tree "-e NCCL_ALGO=Tree"
run_variant algo_ring "-e NCCL_ALGO=Ring"
run_variant proto_ll128 "-e NCCL_PROTO=LL128"
run_variant proto_simple "-e NCCL_PROTO=Simple"
run_variant bufsize_4m "-e NCCL_BUFFSIZE=4194304"

# compact compare of the decode-shaped step line
say "=== step comparison (collective cost/step p50 and slow%) ==="
for d in "$NCCLOUT"/*; do
  lbl=$(basename "$d")
  line=$(grep -h "eager step ms, 88 AR + gaps" "$d"/nccl-forge.txt 2>/dev/null | head -1)
  line2=$(grep -h "graph step ms, 88 AR" "$d"/nccl-forge.txt 2>/dev/null | head -1)
  echo "$lbl | $line"
  echo "$lbl | $line2"
done
say "nccl pre-screen done"
