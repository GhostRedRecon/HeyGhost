#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_ROOT="${HEY_GHOST_INSTALL_ROOT:-/opt/hey-ghost}"
CONFIG_ROOT="${HEY_GHOST_CONFIG_ROOT:-/etc/hey-ghost}"
SERVICE_PATH="${HEY_GHOST_SERVICE_PATH:-/etc/systemd/system/hey-ghost.service}"
WRAPPER_PATH="${HEY_GHOST_WRAPPER_PATH:-/usr/local/bin/heyghost}"
DESKTOP_WRAPPER_PATH="${HEY_GHOST_DESKTOP_WRAPPER_PATH:-/usr/local/bin/heyghost-desktop}"
LOG_DIR="${HEY_GHOST_LOG_DIR:-/var/log/hey-ghost}"
SERVICE_USER="${HEY_GHOST_SERVICE_USER:-heyghost}"
SERVICE_GROUP="${HEY_GHOST_SERVICE_GROUP:-${SERVICE_USER}}"
DESKTOP_APP_ID="heyghost.desktop"
RUN_DEPENDENCIES=1
RUN_TESTS=1
CREATE_DESKTOP_ICON=1
DEPENDENCY_ARGS=()
REPAIR_ATTEMPTED=0

usage() {
  cat <<'EOF'
HeyGhost installer

Usage:
  sudo ./install.sh [options]

What this installs:
  - Debian/Kali/Ubuntu system packages through apt-get
  - Ollama, default Ollama models, whisper.cpp, Whisper models, Piper, Piper voice
  - HeyGhost Python virtual environment and service files
  - heyghost command wrapper and GUI launcher
  - systemd service
  - Desktop launcher icon for the invoking desktop user
  - Post-install checks and test suite

Options:
  --skip-dependencies       Do not run scripts/install_dependencies.sh
  --skip-tests              Do not run HeyGhost post-install tests
  --skip-desktop-icon       Do not create a desktop launcher
  --install-root PATH       Install application files to PATH
  --config-root PATH        Install configuration to PATH
  --log-dir PATH            Write logs under PATH
  --dependency-arg VALUE    Pass one extra argument to scripts/install_dependencies.sh
  -h, --help                Show this help

Examples:
  sudo ./install.sh
  sudo ./install.sh --skip-tests
  sudo ./install.sh --dependency-arg --ollama-model --dependency-arg llama3.2:1b
EOF
}

log() {
  printf '\n[HeyGhost] %s\n' "$*"
}

warn() {
  printf '\n[HeyGhost warning] %s\n' "$*" >&2
}

fail() {
  printf '\n[HeyGhost error] %s\n' "$*" >&2
  exit 1
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --skip-dependencies)
        RUN_DEPENDENCIES=0
        ;;
      --skip-tests)
        RUN_TESTS=0
        ;;
      --skip-desktop-icon)
        CREATE_DESKTOP_ICON=0
        ;;
      --install-root)
        [[ $# -ge 2 ]] || fail "--install-root requires a path"
        INSTALL_ROOT="$2"
        shift
        ;;
      --config-root)
        [[ $# -ge 2 ]] || fail "--config-root requires a path"
        CONFIG_ROOT="$2"
        shift
        ;;
      --log-dir)
        [[ $# -ge 2 ]] || fail "--log-dir requires a path"
        LOG_DIR="$2"
        shift
        ;;
      --dependency-arg)
        [[ $# -ge 2 ]] || fail "--dependency-arg requires a value"
        DEPENDENCY_ARGS+=("$2")
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        fail "Unknown option: $1"
        ;;
    esac
    shift
  done
}

refresh_paths() {
  SERVICE_PATH="${HEY_GHOST_SERVICE_PATH:-/etc/systemd/system/hey-ghost.service}"
  WRAPPER_PATH="${HEY_GHOST_WRAPPER_PATH:-/usr/local/bin/heyghost}"
  DESKTOP_WRAPPER_PATH="${HEY_GHOST_DESKTOP_WRAPPER_PATH:-/usr/local/bin/heyghost-desktop}"
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    fail "Run install.sh as root: sudo ./install.sh"
  fi
}

require_linux() {
  [[ "$(uname -s)" == "Linux" ]] || fail "HeyGhost installer supports Linux only."
  command -v systemctl >/dev/null 2>&1 || fail "systemd is required for service installation."
}

resolve_desktop_user() {
  if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    printf '%s\n' "${SUDO_USER}"
  else
    logname 2>/dev/null || printf 'root\n'
  fi
}

run_dependency_installer() {
  if [[ "${RUN_DEPENDENCIES}" -eq 0 ]]; then
    log "Skipping external dependency installation."
    return
  fi

  local installer="${PROJECT_ROOT}/scripts/install_dependencies.sh"
  [[ -x "${installer}" ]] || fail "Missing executable dependency installer: ${installer}"

  log "Installing system packages, Ollama, Whisper, Piper, and default models."
  HEY_GHOST_INSTALL_ROOT="${INSTALL_ROOT}" "${installer}" --install-root "${INSTALL_ROOT}" "${DEPENDENCY_ARGS[@]}"
}

install_python_requirements() {
  log "Installing Python package requirements."
  "${INSTALL_ROOT}/venv/bin/pip" install --upgrade pip
  "${INSTALL_ROOT}/venv/bin/pip" install -r "${PROJECT_ROOT}/requirements.txt"
}

repair_dependencies() {
  if [[ "${RUN_DEPENDENCIES}" -eq 0 ]]; then
    fail "A post-install check failed, but --skip-dependencies prevents automatic repair."
  fi
  if [[ "${REPAIR_ATTEMPTED}" -eq 1 ]]; then
    fail "Post-install checks still fail after dependency repair."
  fi

  REPAIR_ATTEMPTED=1
  log "A post-install check failed. Reinstalling required dependencies and retrying once."
  run_dependency_installer
  install_python_requirements
  chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${INSTALL_ROOT}" "${LOG_DIR}"
}

create_service_user() {
  log "Creating service user if needed."
  if ! getent group "${SERVICE_GROUP}" >/dev/null 2>&1; then
    groupadd --system "${SERVICE_GROUP}"
  fi

  if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
    useradd --system --home "${INSTALL_ROOT}" --shell /usr/sbin/nologin --gid "${SERVICE_GROUP}" "${SERVICE_USER}"
  fi

  usermod -aG audio "${SERVICE_USER}" || true
}

copy_optional() {
  local src="$1"
  local dst="$2"
  if [[ -e "${src}" ]]; then
    cp -a "${src}" "${dst}"
  fi
}

install_files() {
  log "Installing HeyGhost application files."
  mkdir -p "${INSTALL_ROOT}" "${CONFIG_ROOT}" "${LOG_DIR}"

  rm -rf \
    "${INSTALL_ROOT}/heyghost" \
    "${INSTALL_ROOT}/heyghost.py" \
    "${INSTALL_ROOT}/tests" \
    "${INSTALL_ROOT}/scripts" \
    "${INSTALL_ROOT}/systemd" \
    "${INSTALL_ROOT}/README.md" \
    "${INSTALL_ROOT}/LICENSE" \
    "${INSTALL_ROOT}/MIGRATION_NOTES.md" \
    "${INSTALL_ROOT}/PROJECT_CONTEXT.md" \
    "${INSTALL_ROOT}/requirements.txt" \
    "${INSTALL_ROOT}/config.example.yaml" \
    "${INSTALL_ROOT}/github.txt"

  cp -a "${PROJECT_ROOT}/heyghost" "${INSTALL_ROOT}/heyghost"
  cp -a "${PROJECT_ROOT}/heyghost.py" "${INSTALL_ROOT}/heyghost.py"
  cp -a "${PROJECT_ROOT}/requirements.txt" "${INSTALL_ROOT}/requirements.txt"
  copy_optional "${PROJECT_ROOT}/tests" "${INSTALL_ROOT}/tests"
  copy_optional "${PROJECT_ROOT}/scripts" "${INSTALL_ROOT}/scripts"
  copy_optional "${PROJECT_ROOT}/systemd" "${INSTALL_ROOT}/systemd"
  copy_optional "${PROJECT_ROOT}/README.md" "${INSTALL_ROOT}/README.md"
  copy_optional "${PROJECT_ROOT}/LICENSE" "${INSTALL_ROOT}/LICENSE"
  copy_optional "${PROJECT_ROOT}/MIGRATION_NOTES.md" "${INSTALL_ROOT}/MIGRATION_NOTES.md"
  copy_optional "${PROJECT_ROOT}/PROJECT_CONTEXT.md" "${INSTALL_ROOT}/PROJECT_CONTEXT.md"
  copy_optional "${PROJECT_ROOT}/config.example.yaml" "${INSTALL_ROOT}/config.example.yaml"
  copy_optional "${PROJECT_ROOT}/github.txt" "${INSTALL_ROOT}/github.txt"

  if [[ ! -f "${CONFIG_ROOT}/config.yaml" ]]; then
    cp "${PROJECT_ROOT}/config.example.yaml" "${CONFIG_ROOT}/config.yaml"
  else
    log "Keeping existing ${CONFIG_ROOT}/config.yaml"
  fi

  python3 -m venv "${INSTALL_ROOT}/venv"
  install_python_requirements

  mkdir -p \
    "${INSTALL_ROOT}/bin" \
    "${INSTALL_ROOT}/models/whisper" \
    "${INSTALL_ROOT}/models/piper" \
    "${INSTALL_ROOT}/knowledge" \
    "${INSTALL_ROOT}/shared"

  chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${INSTALL_ROOT}" "${LOG_DIR}"
  chmod 755 "${INSTALL_ROOT}" "${LOG_DIR}"
}

install_wrapper() {
  log "Installing command wrapper at ${WRAPPER_PATH}."
  cat > "${WRAPPER_PATH}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export HEY_GHOST_INSTALL_ROOT="\${HEY_GHOST_INSTALL_ROOT:-${INSTALL_ROOT}}"
export HEY_GHOST_CONFIG_ROOT="\${HEY_GHOST_CONFIG_ROOT:-${CONFIG_ROOT}}"
export HEY_GHOST_LOG_DIR="\${HEY_GHOST_LOG_DIR:-${LOG_DIR}}"
export HEY_GHOST_CONFIG="\${HEY_GHOST_CONFIG:-${CONFIG_ROOT}/config.yaml}"
exec "${INSTALL_ROOT}/venv/bin/python" "${INSTALL_ROOT}/heyghost.py" --config "\${HEY_GHOST_CONFIG}" "\$@"
EOF
  chmod +x "${WRAPPER_PATH}"
}

install_desktop_wrapper() {
  log "Installing desktop GUI launcher at ${DESKTOP_WRAPPER_PATH}."
  cat > "${DESKTOP_WRAPPER_PATH}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
STATE_DIR="\${XDG_STATE_HOME:-\${HOME}/.local/state}/heyghost"
DATA_DIR="\${XDG_DATA_HOME:-\${HOME}/.local/share}/heyghost"
SHARED_DIR="\${STATE_DIR}/shared"
LOG_DIR="\${STATE_DIR}/logs"
USER_CONFIG="\${STATE_DIR}/config.yaml"
SOURCE_CONFIG="\${HEY_GHOST_CONFIG:-${CONFIG_ROOT}/config.yaml}"
LAUNCH_LOG="\${STATE_DIR}/desktop-launch.log"
mkdir -p "\${SHARED_DIR}" "\${LOG_DIR}" "\${DATA_DIR}/knowledge"
{
  printf '\n[%s] Launching HeyGhost desktop GUI\n' "\$(date -Is)"
  "${INSTALL_ROOT}/venv/bin/python" - "\${SOURCE_CONFIG}" "\${USER_CONFIG}" "\${STATE_DIR}" "\${DATA_DIR}" <<'HEY_GHOST_DESKTOP_CONFIG'
from pathlib import Path
import sys
import yaml

source = Path(sys.argv[1])
target = Path(sys.argv[2])
state_dir = Path(sys.argv[3])
data_dir = Path(sys.argv[4])
shared_dir = state_dir / "shared"
log_dir = state_dir / "logs"
knowledge_dir = data_dir / "knowledge"
for directory in (shared_dir, log_dir, knowledge_dir):
    directory.mkdir(parents=True, exist_ok=True)

with source.open("r", encoding="utf-8") as handle:
    config = yaml.safe_load(handle)

config.setdefault("tts", {})["speaker_wav_path"] = str(shared_dir / "heyghost_response.wav")
config.setdefault("wake_word", {})["dev_trigger_file"] = str(shared_dir / "heyghost_wake")
config.setdefault("conversation", {})["memory_path"] = str(shared_dir / "conversation-memory.sqlite3")
config.setdefault("logging", {})["log_file"] = str(log_dir / "hey-ghost.log")
config.setdefault("logging", {})["debug_events_file"] = str(shared_dir / "debug-events.jsonl")
config.setdefault("rag", {})["index_path"] = str(shared_dir / "rag-index.sqlite3")
config.setdefault("rag", {})["knowledge_dir"] = str(knowledge_dir)

target.parent.mkdir(parents=True, exist_ok=True)
with target.open("w", encoding="utf-8") as handle:
    yaml.safe_dump(config, handle, sort_keys=False)
HEY_GHOST_DESKTOP_CONFIG
  HEY_GHOST_CONFIG="\${USER_CONFIG}" exec "${WRAPPER_PATH}" desktop
} >> "\${LAUNCH_LOG}" 2>&1
EOF
  chmod +x "${DESKTOP_WRAPPER_PATH}"
}

install_service() {
  log "Installing systemd service."
  cat > "${SERVICE_PATH}" <<EOF
[Unit]
Description=HeyGhost Local Voice Assistant
After=network.target sound.target ollama.service
Wants=network.target ollama.service

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
SupplementaryGroups=audio
WorkingDirectory=${INSTALL_ROOT}
Environment=HEY_GHOST_INSTALL_ROOT=${INSTALL_ROOT}
Environment=HEY_GHOST_CONFIG_ROOT=${CONFIG_ROOT}
Environment=HEY_GHOST_LOG_DIR=${LOG_DIR}
Environment=HEY_GHOST_CONFIG=${CONFIG_ROOT}/config.yaml
ExecStart=${INSTALL_ROOT}/venv/bin/python ${INSTALL_ROOT}/heyghost.py --config ${CONFIG_ROOT}/config.yaml run
Restart=on-failure
RestartSec=2
NoNewPrivileges=true
ProtectSystem=full
ProtectHome=false
ReadWritePaths=${LOG_DIR} /tmp ${INSTALL_ROOT}

[Install]
WantedBy=multi-user.target
EOF
}

enable_service() {
  log "Enabling hey-ghost.service."
  systemctl daemon-reload
  systemctl enable hey-ghost.service
}

create_desktop_icon() {
  if [[ "${CREATE_DESKTOP_ICON}" -eq 0 ]]; then
    log "Skipping desktop launcher creation."
    return
  fi

  local desktop_user desktop_home desktop_dir applications_dir launcher user_launcher
  desktop_user="$(resolve_desktop_user)"
  desktop_home="$(getent passwd "${desktop_user}" | cut -d: -f6)"

  if [[ -z "${desktop_home}" || ! -d "${desktop_home}" ]]; then
    warn "Could not find home directory for ${desktop_user}; skipping desktop launcher."
    return
  fi

  desktop_dir="${desktop_home}/Desktop"
  applications_dir="${desktop_home}/.local/share/applications"
  mkdir -p "${desktop_dir}" "${applications_dir}"

  launcher="${applications_dir}/${DESKTOP_APP_ID}"
  cat > "${launcher}" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=HeyGhost
Comment=Local-first Linux voice assistant
Exec=${DESKTOP_WRAPPER_PATH}
Terminal=false
Icon=audio-input-microphone
Categories=Utility;Audio;Accessibility;
StartupNotify=true
EOF

  user_launcher="${desktop_dir}/${DESKTOP_APP_ID}"
  cp "${launcher}" "${user_launcher}"
  chmod +x "${launcher}" "${user_launcher}"
  chown "${desktop_user}:${desktop_user}" "${launcher}" "${user_launcher}" 2>/dev/null || chown "${desktop_user}" "${launcher}" "${user_launcher}" || true

  if command -v gio >/dev/null 2>&1; then
    sudo -u "${desktop_user}" gio set "${user_launcher}" metadata::trusted true >/dev/null 2>&1 || true
  fi

  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${applications_dir}" >/dev/null 2>&1 || true
  fi

  log "Created desktop launcher: ${user_launcher}"
}

verify_dependency_files() {
  log "Checking installed external runtime files."
  local missing=0
  local required=(
    "${INSTALL_ROOT}/bin/whisper-cli"
    "${INSTALL_ROOT}/models/whisper/ggml-tiny.en.bin"
    "${INSTALL_ROOT}/bin/piper"
    "${INSTALL_ROOT}/models/piper/en_US-lessac-medium.onnx"
  )

  for item in "${required[@]}"; do
    if [[ ! -e "${item}" ]]; then
      warn "Missing expected dependency file: ${item}"
      missing=1
    fi
  done

  return "${missing}"
}

verify_python_imports() {
  log "Checking Python runtime imports."
  PYTHONPATH="${INSTALL_ROOT}" "${INSTALL_ROOT}/venv/bin/python" - <<'HEY_GHOST_PY' || return 1
import importlib

modules = (
    "yaml",
    "numpy",
    "sounddevice",
    "webrtcvad",
    "heyghost.app",
    "heyghost.wake.wake_word",
    "tkinter",
)
for module in modules:
    importlib.import_module(module)
print("Python import check passed")
HEY_GHOST_PY
}

run_post_install_tests() {
  if [[ "${RUN_TESTS}" -eq 0 ]]; then
    log "Skipping tests."
    return 0
  fi

  log "Running HeyGhost test suite."
  if [[ -f "${INSTALL_ROOT}/tests/run_tests.py" ]]; then
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${INSTALL_ROOT}" \
      "${INSTALL_ROOT}/venv/bin/python" "${INSTALL_ROOT}/tests/run_tests.py" || return 1
  else
    warn "Tests were not installed; skipping Python test suite."
  fi

  log "Checking installed configuration can load."
  HEY_GHOST_CONFIG="${CONFIG_ROOT}/config.yaml" PYTHONPATH="${INSTALL_ROOT}" \
    "${INSTALL_ROOT}/venv/bin/python" - <<'HEY_GHOST_PY' || return 1
import os
from heyghost.config import load_config
load_config(os.environ["HEY_GHOST_CONFIG"])
print("Config load check passed")
HEY_GHOST_PY

  if ! command -v ollama >/dev/null 2>&1; then
    warn "Ollama command was not found after dependency installation."
    return 1
  fi
  if ! ollama list >/dev/null 2>&1; then
    warn "Ollama is installed but not responding."
    return 1
  fi
  log "Ollama is installed and responding."

  log "Checking Piper binary."
  "${INSTALL_ROOT}/bin/piper" --help >/dev/null 2>&1 || return 1

  log "Checking whisper.cpp binary."
  "${INSTALL_ROOT}/bin/whisper-cli" --help >/dev/null 2>&1 || return 1
}

run_all_post_install_checks() {
  verify_dependency_files && verify_python_imports && run_post_install_tests
}

run_checks_with_repair() {
  if run_all_post_install_checks; then
    return
  fi

  repair_dependencies
  run_all_post_install_checks || fail "Post-install checks failed after dependency repair."
}

launch_heyghost_app() {
  log "Launching HeyGhost service."
  systemctl restart hey-ghost.service

  if systemctl is-active --quiet hey-ghost.service; then
    log "HeyGhost service is running."
    return
  fi

  systemctl status hey-ghost.service --no-pager || true
  fail "HeyGhost service failed to start."
}

print_next_steps() {
  cat <<EOF

Install complete.

Installed paths:
  App:      ${INSTALL_ROOT}
  Config:   ${CONFIG_ROOT}/config.yaml
  Logs:     ${LOG_DIR}
  Command:  ${WRAPPER_PATH}
  GUI:      ${DESKTOP_WRAPPER_PATH}
  Service:  hey-ghost.service

Start and test HeyGhost:
  heyghost start
  heyghost status
  heyghost trigger

Desktop launcher:
  A HeyGhost icon was created on the desktop for the user who ran sudo.
  Double-click it to open the GhostWave GUI, then click the window or press Space to start listening.
  If your desktop asks for permission, choose "Allow Launching" or "Trust and Launch".
  Launch logs are written to ~/.local/state/heyghost/desktop-launch.log.

Useful commands:
  heyghost debug-window
  heyghost stop
  journalctl -u hey-ghost.service -f
EOF
}

parse_args "$@"
refresh_paths
require_root
require_linux
run_dependency_installer
create_service_user
install_files
install_wrapper
install_desktop_wrapper
install_service
enable_service
create_desktop_icon
run_checks_with_repair
launch_heyghost_app
print_next_steps
