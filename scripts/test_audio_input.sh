#!/usr/bin/env bash
set -euo pipefail

OUTPUT="/tmp/heyghost_mic_test.wav"

echo "Recording 4 seconds from default input device..."
arecord -f S16_LE -r 16000 -c 1 -d 4 "${OUTPUT}"
echo "Saved ${OUTPUT}"
aplay "${OUTPUT}"
