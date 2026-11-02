#!/bin/bash
set -euo pipefail
cd /
cache=(--enable-prefix-caching)
case "$#:${1-}" in
  0:) ;;
  1:--performance) cache=(--no-enable-prefix-caching) ;;
  *) echo 'Usage: start-model.sh [--performance]' >&2; exit 2 ;;
esac
VLLM_HOST_IP=$(/opt/conda/bin/python -c 'import fcntl,socket,struct; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); print(socket.inet_ntoa(fcntl.ioctl(s.fileno(),0x8915,struct.pack("256s",b"inbond1"))[20:24]))')
export VLLM_HOST_IP
role=()
case "$VLLM_HOST_IP" in
  192.168.2.101) node=0 ;;
  192.168.2.102) node=1; role=(--headless) ;;
  *) echo 'This launcher requires the verified mx-101/mx-102 inbond1 topology.' >&2; exit 2 ;;
esac
export MCCL_SOCKET_IFNAME=inbond1 GLOO_SOCKET_IFNAME=inbond1
export VLLM_FL_USE_FLAGGEMS_VLLM=1 OMP_NUM_THREADS=1
exec /opt/conda/bin/python -m vllm.entrypoints.cli.main serve \
  /public-flash/models/GLM-5.3-Flash-BF16 \
  --served-model-name glm5.3-flash --dtype bfloat16 \
  --tensor-parallel-size 8 --pipeline-parallel-size 2 \
  --distributed-executor-backend mp --nnodes 2 --node-rank "$node" \
  --master-addr 192.168.2.101 --master-port 29653 \
  --max-model-len 65536 --max-num-seqs 8 --max-num-batched-tokens 2048 \
  --mamba-cache-mode align --reasoning-parser glm45 \
  --compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE"}' \
  --host 0.0.0.0 --port 18530 "${cache[@]}" "${role[@]}"
