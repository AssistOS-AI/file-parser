#!/bin/sh
# One detached writer: the resumed matrix, then the adaptive reruns (each appends to its own log).
cd /home/research/phase0
echo $$ > logs/followup-continue.pid
sh tools/followup-resume.sh >> logs/followup-resume.log 2>&1
sh tools/followup-reruns.sh >> logs/followup-reruns.log 2>&1
echo "== continue done $(date +%T)" >> logs/followup-resume.log
rm -f logs/followup-continue.pid
