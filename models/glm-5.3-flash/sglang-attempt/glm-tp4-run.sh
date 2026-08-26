#!/bin/bash
# GLM-5.3-Flash TP4 bring-up on DGX Spark cluster.
# Inter-node traffic pinned to the wired CX-7 fabric (192.168.2.x, enp1s0f1np1 / RoCE HCA rocep1s0f1).
# Usage: glm-tp4-run.sh <node-rank 0..3>   (rank 0 = forge = 192.168.2.1)
set -u
RANK="${1:?node rank required}"
MODEL=/models/glm
IMAGE=lmsysorg/sglang:glm-5.3-flash

docker rm -f glm53-tp4 2>/dev/null
docker run -d --name glm53-tp4 \
  --gpus all --network host --ipc host --shm-size 64gb \
  --device /dev/infiniband \
  --cap-add IPC_LOCK \
  --ulimit nofile=1048576:1048576 --ulimit memlock=-1 --ulimit stack=67108864 \
  -v /home/jun/models/glm-5.3-flash:$MODEL:ro \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  -e NCCL_NET=IB -e NCCL_IB_DISABLE=0 -e NCCL_IB_HCA=rocep1s0f1 \
  -e NCCL_SOCKET_IFNAME=enp1s0f1np1 -e GLOO_SOCKET_IFNAME=enp1s0f1np1 \
  -e NCCL_IB_ADDR_FAMILY=AF_INET -e NCCL_IB_ROCE_VERSION_NUM=2 \
  -e NCCL_IB_ADDR_RANGE=192.168.2.0/24 -e NCCL_CROSS_NIC=1 \
  -e NCCL_NVLS_ENABLE=0 -e NCCL_IGNORE_CPU_AFFINITY=1 -e NCCL_DEBUG=WARN \
  $IMAGE python3 -m sglang.launch_server \
    --model-path $MODEL --served-model-name glm-5.3-flash \
    --nnodes 4 --node-rank $RANK --dist-init-addr 192.168.2.1:5000 \
    --tp-size 4 \
    --quantization fp8 --kv-cache-dtype bfloat16 \
    --attention-backend dsa --dsa-prefill-backend flashmla_sparse --dsa-decode-backend flashmla_sparse \
    --linear-attn-backend triton \
    --moe-runner-backend deep_gemm \
    --disable-shared-experts-fusion --disable-prefill-cuda-graph \
    --chunked-prefill-size 8192 --max-prefill-tokens 8192 \
    --max-running-requests 16 \
    --speculative-algorithm NEXTN --speculative-num-steps 5 \
    --speculative-eagle-topk 1 --speculative-num-draft-tokens 6 --speculative-adaptive \
    --speculative-draft-attention-backend triton \
    --mem-fraction-static 0.85 \
    --host 0.0.0.0 --port 30000
echo "launched glm53-tp4 rank=$RANK"
