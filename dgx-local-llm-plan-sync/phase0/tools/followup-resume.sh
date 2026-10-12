#!/bin/sh
# Resume of the safety follow-up matrix after the 2026-09-28 21:31 session restart (tools/followup.sh stopped
# in qwen-c256k-np1-mtpoff-cram8192-r1; that attempt is marked INTERRUPTED and kept unchanged). Runs only
# what followup.sh had not completed, in its order; the interrupted configuration gets a new attempt name
# (-a2). A run whose output prefix already has any file is refused, so no raw record is ever overwritten.
# Every run holds the exclusive memory lock itself (harness v5, stop_latency v2).
set -u
cd /home/research/phase0
B=l1/llama-b11159
M120=models/gpt-oss-120b-MXFP4.gguf
MQ=models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf
OUT=results/followup
PATTERNS="--pattern greedy --pattern prefill --pattern parallel --pattern coldparallel --pattern longgen"
MTP="--spec-type draft-mtp --spec-draft-n-max 3"

fresh() {
  if ls "$1"* >/dev/null 2>&1; then
    echo "== REFUSED $(date +%T): $1 already has files; not overwriting"
    return 1
  fi
  return 0
}

qwen() { # rep mtp cram ctxkind [attempt-suffix]
  rep=$1; mtp=$2; cram=$3; kind=$4; suffix=${5:-}
  extra=""; [ "$mtp" = on ] && extra="$MTP"
  if [ "$kind" = c128k ]; then
    out=$OUT/qwen-c128k-np4-mtp$mtp-cram$cram-r$rep$suffix
    fresh "$out" || return 0
    echo "== qwen c128k np4 mtp $mtp cache-ram $cram rep $rep$suffix $(date +%T)"
    python3 tools/serve_check2.py --bin $B --model $MQ --out "$out" --ctx 131072 --np 4 --cache-ram $cram --cold --extra="$extra" $PATTERNS 2>&1 | tail -1
  else
    out=$OUT/qwen-c256k-np1-mtp$mtp-cram$cram-r$rep$suffix
    fresh "$out" || return 0
    echo "== qwen c256k np1 mtp $mtp cache-ram $cram rep $rep$suffix $(date +%T)"
    python3 tools/serve_check2.py --bin $B --model $MQ --out "$out" --ctx 262144 --np 1 --cache-ram $cram --cold --extra="$extra" --pattern greedy --pattern prefill --pattern longgen 2>&1 | tail -1
  fi
}

echo "== resume start $(date +%T)"
# rep 1: mtp off, cram 8192, c128k is complete; c256k was interrupted.
qwen 1 off 8192 c256k -a2
qwen 1 off 1 c128k; qwen 1 off 1 c256k
qwen 1 on 8192 c128k; qwen 1 on 8192 c256k
qwen 1 on 1 c128k; qwen 1 on 1 c256k
# rep 2: everything.
for mtp in off on; do
  for cram in 8192 1; do
    qwen 2 $mtp $cram c128k; qwen 2 $mtp $cram c256k
  done
done
for rep in 1 2; do
  for when in load active; do
    for sig in KILL TERM; do
      out=$OUT/stop-120b-$when-$sig-r$rep
      fresh "$out" || continue
      echo "== stop 120b $when $sig rep $rep $(date +%T)"
      python3 tools/stop_latency.py --bin $B --model $M120 --out "$out" --when $when --signal $sig --ctx 131072 --np 4 --at 8 2>&1 | tail -1
    done
  done
done
echo "== resume done $(date +%T)"
