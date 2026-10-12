#!/bin/sh
# usage: bench.sh BIN_DIR LABEL MODEL_FILE  -> results/LABEL-<model>.jsonl (+ memory samples)
set -eu
bin=$1; label=$2; model=$3
out=/home/research/phase0/results/$label-$(basename "$model" .gguf)
mkdir -p /home/research/phase0/results
python3 /home/research/phase0/tools/memsample.py "$out-mem" 250 & sampler=$!
LD_LIBRARY_PATH= /home/research/phase0/tools/gpurun "$bin/llama-bench" -m "$model" -ngl 99 -b 2048 -ub 2048 -fa on -t 10 \
    -p 2048 -n 32 -d 0,32768 -lm none,dio -r 5 -o jsonl > "$out.jsonl" 2> "$out.err" || echo "llama-bench exit $?"
kill -TERM $sampler; wait $sampler || true
