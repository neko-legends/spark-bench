#!/usr/bin/env bash
# Bring up the 4-node TP4 GLM-5.3-Flash (NVFP4) stack.
# Run from forge. Head starts first (waits for workers), workers follow.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE="docker compose -f $DIR/../docker-compose.glm53-tp4.yml"

case "${1:-up}" in
  up)
    echo "head (forge, rank 0) starting..."
    $COMPOSE --env-file "$DIR/../.env.node-0" up -d
    sleep 5
    for n in 1 2 3; do
      host=$(grep -oP 'node \K[13](?= = )' /dev/null 2>/dev/null; true)
    done
    for pair in "anvil 1" "ember 2" "flame 3"; do
      set -- $pair
      echo "worker $1 (rank $2) starting..."
      ssh -o BatchMode=yes -o ConnectTimeout=6 "$1" \
        "cd $DIR/.. && $COMPOSE --env-file $DIR/../.env.node-$2 up -d"
    done
    echo "all nodes launched. Head logs: docker logs -f glm53-vllm"
    ;;
  down)
    for h in forge anvil ember flame; do
      ssh -o BatchMode=yes -o ConnectTimeout=6 "$h" "docker rm -f \$(docker ps -aq --filter name=vllm-glm53) 2>/dev/null" || true
    done
    echo "stopped"
    ;;
esac
