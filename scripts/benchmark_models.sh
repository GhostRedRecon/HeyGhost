#!/usr/bin/env bash
set -euo pipefail

MODELS=(
  "qwen2.5:0.5b"
  "gemma3:1b"
  "smollm2:135m"
  "llama3.2:1b"
)

PROMPT="Reply in one short sentence: What is the capital of Spain?"

for model in "${MODELS[@]}"; do
  echo "=== ${model} ==="
  /usr/bin/time -f "elapsed=%E rss=%MKB" \
    curl -fsS http://localhost:11434/api/generate \
      -H 'Content-Type: application/json' \
      -d "{\"model\":\"${model}\",\"prompt\":\"${PROMPT}\",\"stream\":false,\"options\":{\"num_ctx\":512,\"num_predict\":32,\"temperature\":0.2}}"
  echo
done
