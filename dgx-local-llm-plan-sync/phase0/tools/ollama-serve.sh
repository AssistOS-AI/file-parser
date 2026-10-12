#!/bin/sh
# Ollama for the Phase 0 gate: loopback, non-default port, the agent adapter's environment, a scratch JIT cache.
exec env -i PATH=/usr/bin:/bin HOME=/home/research/phase0/ollama-home LANG=C.UTF-8 \
  OLLAMA_MODELS=/home/research/phase0/ollama-models OLLAMA_HOST=127.0.0.1:11535 \
  OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_KV_CACHE_TYPE=f16 OLLAMA_CONTEXT_LENGTH=8192 \
  OLLAMA_KEEP_ALIVE=30m OLLAMA_NO_CLOUD=1 OLLAMA_DEBUG=1 \
  CUDA_CACHE_PATH=/home/research/phase0/ollama-jit "$@" \
  /home/research/phase0/tools/gpurun /home/research/phase0/ollama/bin/ollama serve
