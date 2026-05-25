#!/usr/bin/env bash
set -euo pipefail

MODEL="${1:-qwen2.5:0.5b}"

curl -fsS http://localhost:11434/api/generate \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"${MODEL}\",\"prompt\":\"Reply in one short sentence: say hello from Ghost.\",\"stream\":false,\"options\":{\"num_ctx\":2048,\"num_predict\":80,\"temperature\":0.4}}"
