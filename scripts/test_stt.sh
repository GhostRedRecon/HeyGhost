#!/usr/bin/env bash
set -euo pipefail

WHISPER_BIN="${WHISPER_BIN:-/opt/hey-ghost/bin/whisper-cli}"
WHISPER_MODEL="${WHISPER_MODEL:-/opt/hey-ghost/models/whisper/ggml-tiny.en.bin}"
INPUT_WAV="${1:-/tmp/heyghost_mic_test.wav}"

"${WHISPER_BIN}" \
  -m "${WHISPER_MODEL}" \
  -f "${INPUT_WAV}" \
  -l en \
  -otxt \
  -of /tmp/heyghost_stt_test

cat /tmp/heyghost_stt_test.txt
