#!/usr/bin/env bash
set -euo pipefail

PIPER_BIN="${PIPER_BIN:-/opt/hey-ghost/bin/piper}"
PIPER_MODEL="${PIPER_MODEL:-/opt/hey-ghost/models/piper/en_US-lessac-medium.onnx}"
OUTPUT_WAV="${OUTPUT_WAV:-/tmp/heyghost_tts_test.wav}"

printf 'Hey Ghost text to speech test.\n' | "${PIPER_BIN}" \
  --model "${PIPER_MODEL}" \
  --output_file "${OUTPUT_WAV}"

aplay "${OUTPUT_WAV}"
