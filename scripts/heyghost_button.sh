#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:0}"
if [[ -z "${XAUTHORITY:-}" && -n "${HOME:-}" && -f "${HOME}/.Xauthority" ]]; then
  export XAUTHORITY="${HOME}/.Xauthority"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/heyghost"
LOG_FILE="${LOG_DIR}/heyghost-ui.log"
LOCK_FILE="${LOG_DIR}/heyghost-desktop.lock"

activate_existing_window() {
  if command -v xdotool >/dev/null 2>&1; then
    local window_id
    window_id="$(xdotool search --name "HeyGhost - GhostWave" 2>/dev/null | tail -n 1 || true)"
    if [[ -n "${window_id}" ]]; then
      xdotool windowactivate "${window_id}" 2>/dev/null || true
      xdotool windowraise "${window_id}" 2>/dev/null || true
      return 0
    fi
  fi
  return 1
}

mkdir -p "${LOG_DIR}"

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  if activate_existing_window; then
    echo "$(date --iso-8601=seconds) Focused existing HeyGhost desktop session." >>"${LOG_FILE}"
  else
    echo "$(date --iso-8601=seconds) HeyGhost desktop session is already running, but no window was found." >>"${LOG_FILE}"
  fi
  exit 0
fi

if command -v heyghost >/dev/null 2>&1; then
  exec heyghost desktop >>"${LOG_FILE}" 2>&1
fi

exec python3 "${PROJECT_ROOT}/heyghost.py" --config "${HEY_GHOST_CONFIG:-${PROJECT_ROOT}/config.yaml}" desktop >>"${LOG_FILE}" 2>&1
