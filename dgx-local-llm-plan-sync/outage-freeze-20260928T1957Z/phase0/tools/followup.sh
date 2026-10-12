#!/bin/sh
# Safety follow-up measurement matrix (plans/phase0-safety-followup_codex.md). Sequential; nothing else runs.
set -u
cd /home/research/phase0
B=l1/llama-b11159
M120=models/gpt-oss-120b-MXFP4.gguf
M20=models/gpt-oss-20b-MXFP4.gguf
OUT=results/followup
mkdir -p "$OUT"
PATTERNS="--pattern greedy --pattern prefill --pattern parallel --pattern coldparallel --pattern longgen"
for rep in 1 2; do
  for cram in 8192 4096 1; do
    echo "== 120b c128k np4 cache-ram $cram rep $rep $(date +%T)"
    python3 tools/serve_check2.py --bin $B --model $M120 --out $OUT/120b-c128k-np4-cram$cram-r$rep --ctx 131072 --np 4 --cache-ram $cram --cold $PATTERNS 2>&1 | tail -1
  done
  for cram in 8192 1; do
    echo "== 20b c128k np4 cache-ram $cram rep $rep $(date +%T)"
    python3 tools/serve_check2.py --bin $B --model $M20 --out $OUT/20b-c128k-np4-cram$cram-r$rep --ctx 131072 --np 4 --cache-ram $cram --cold $PATTERNS 2>&1 | tail -1
  done
done
MQ=models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf
MTP="--spec-type draft-mtp --spec-draft-n-max 3"
for rep in 1 2; do
  for mtp in off on; do
    extra=""; [ "$mtp" = on ] && extra="$MTP"
    for cram in 8192 1; do
      echo "== qwen c128k np4 mtp $mtp cache-ram $cram rep $rep $(date +%T)"
      python3 tools/serve_check2.py --bin $B --model $MQ --out $OUT/qwen-c128k-np4-mtp$mtp-cram$cram-r$rep --ctx 131072 --np 4 --cache-ram $cram --cold --extra="$extra" $PATTERNS 2>&1 | tail -1
      echo "== qwen c256k np1 mtp $mtp cache-ram $cram rep $rep $(date +%T)"
      python3 tools/serve_check2.py --bin $B --model $MQ --out $OUT/qwen-c256k-np1-mtp$mtp-cram$cram-r$rep --ctx 262144 --np 1 --cache-ram $cram --cold --extra="$extra" --pattern greedy --pattern prefill --pattern longgen 2>&1 | tail -1
    done
  done
done
for rep in 1 2; do
  for when in load active; do
    for sig in KILL TERM; do
      echo "== stop 120b $when $sig rep $rep $(date +%T)"
      python3 tools/stop_latency.py --bin $B --model $M120 --out $OUT/stop-120b-$when-$sig-r$rep --when $when --signal $sig --ctx 131072 --np 4 --at 8 2>&1 | tail -1
    done
  done
done
echo "== done $(date +%T)"
