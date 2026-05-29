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
WHISPER_CPP_REF="${WHISPER_CPP_REF:-master}"
WHISPER_MODELS=("tiny.en" "base.en")
OLLAMA_MODELS=("qwen2.5:0.5b" "nomic-embed-text")
PIPER_VERSION="${PIPER_VERSION:-1.2.0}"
PIPER_VOICE="${PIPER_VOICE:-en_US-lessac-medium}"
PIPER_VOICE_BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
BUILD_DIR="${HEY_GHOST_BUILD_DIR:-/tmp/heyghost-deps}"
RUN_DEPENDENCIES=1
RUN_TESTS=1
CREATE_DESKTOP_ICON=1
SKIP_OLLAMA=0
SKIP_WHISPER=0
SKIP_PIPER=0
REPAIR_ATTEMPTED=0
REPORT_NOTES=()

usage() {
  cat <<'EOF'
HeyGhost one-file installer

Usage:
  sudo ./install.sh [options]

What this installs and verifies:
  - Debian/Kali/Ubuntu system packages through apt-get
  - Ollama and local models
  - whisper.cpp and Whisper speech-to-text models
  - Piper text-to-speech and voice model
  - HeyGhost Python virtual environment and Python packages
  - HeyGhost app files, config, command wrapper, desktop GUI launcher, and systemd service
  - Full post-install checks, Python tests, and a final beginner-friendly report

Options:
  --skip-dependencies       Do not install external system/runtime dependencies
  --skip-tests              Do not run HeyGhost post-install tests
  --skip-desktop-icon       Do not create a desktop launcher
  --skip-ollama             Do not install Ollama or pull Ollama models
  --skip-whisper            Do not build whisper.cpp or download Whisper models
  --skip-piper              Do not install Piper or its voice model
  --ollama-model MODEL      Pull an additional Ollama model. Can be repeated
  --whisper-model MODEL     Download an additional whisper.cpp model. Can be repeated
  --piper-version VERSION   Piper release version, default: 1.2.0
  --piper-voice VOICE       Piper voice name, default: en_US-lessac-medium
  --install-root PATH       Install application files to PATH
  --config-root PATH        Install configuration to PATH
  --log-dir PATH            Write logs under PATH
  --dependency-arg VALUE    Backward-compatible dependency option passthrough
  -h, --help                Show this help

Examples:
  sudo ./install.sh
  sudo ./install.sh --skip-tests
  sudo ./install.sh --ollama-model llama3.2:1b
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

add_report_note() {
  REPORT_NOTES+=("$*")
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
      --skip-ollama)
        SKIP_OLLAMA=1
        ;;
      --skip-whisper)
        SKIP_WHISPER=1
        ;;
      --skip-piper)
        SKIP_PIPER=1
        ;;
      --ollama-model)
        [[ $# -ge 2 ]] || fail "--ollama-model requires a model name"
        OLLAMA_MODELS+=("$2")
        shift
        ;;
      --whisper-model)
        [[ $# -ge 2 ]] || fail "--whisper-model requires a model name"
        WHISPER_MODELS+=("$2")
        shift
        ;;
      --piper-version)
        [[ $# -ge 2 ]] || fail "--piper-version requires a version"
        PIPER_VERSION="$2"
        shift
        ;;
      --piper-voice)
        [[ $# -ge 2 ]] || fail "--piper-voice requires a voice name"
        PIPER_VOICE="$2"
        shift
        ;;
      --dependency-arg)
        [[ $# -ge 2 ]] || fail "--dependency-arg requires a value"
        case "$2" in
          --skip-ollama) SKIP_OLLAMA=1 ;;
          --skip-whisper) SKIP_WHISPER=1 ;;
          --skip-piper) SKIP_PIPER=1 ;;
          --ollama-model|--whisper-model|--piper-version|--piper-voice)
            local_value_index=3
            if [[ "${3:-}" == "--dependency-arg" ]]; then
              local_value_index=4
              [[ $# -ge 4 ]] || fail "$2 requires a value after --dependency-arg"
            else
              [[ $# -ge 3 ]] || fail "$2 requires a value after --dependency-arg"
            fi
            case "$2" in
              --ollama-model) OLLAMA_MODELS+=("${!local_value_index}") ;;
              --whisper-model) WHISPER_MODELS+=("${!local_value_index}") ;;
              --piper-version) PIPER_VERSION="${!local_value_index}" ;;
              --piper-voice) PIPER_VOICE="${!local_value_index}" ;;
            esac
            if [[ "${local_value_index}" -eq 4 ]]; then
              shift 2
            else
              shift
            fi
            ;;
          *)
            fail "Unsupported --dependency-arg value now that install.sh is self-contained: $2"
            ;;
        esac
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

run_as_invoking_user() {
  if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    sudo -u "${SUDO_USER}" env HOME="$(getent passwd "${SUDO_USER}" | cut -d: -f6)" "$@"
  else
    "$@"
  fi
}

install_system_packages() {
  log "Installing Debian/Kali/Ubuntu system packages."
  apt-get update
  apt-get install -y \
    git \
    curl \
    wget \
    ca-certificates \
    build-essential \
    cmake \
    pkg-config \
    python3 \
    python3-venv \
    python3-pip \
    python3-tk \
    portaudio19-dev \
    ffmpeg \
    alsa-utils
  add_report_note "System packages installed or already present."
}

prepare_dependency_dirs() {
  mkdir -p \
    "${INSTALL_ROOT}/bin" \
    "${INSTALL_ROOT}/lib" \
    "${INSTALL_ROOT}/models/whisper" \
    "${INSTALL_ROOT}/models/piper" \
    "${INSTALL_ROOT}/knowledge" \
    "${INSTALL_ROOT}/shared" \
    "${BUILD_DIR}"
}

install_ollama_dependency() {
  if [[ "${SKIP_OLLAMA}" -eq 1 ]]; then
    log "Skipping Ollama."
    add_report_note "Ollama installation skipped."
    return
  fi

  if ! command -v ollama >/dev/null 2>&1; then
    log "Installing Ollama."
    curl -fsSL https://ollama.com/install.sh | sh
    add_report_note "Ollama installed."
  else
    log "Ollama already installed."
    add_report_note "Ollama already installed."
  fi

  if command -v systemctl >/dev/null 2>&1; then
    systemctl enable --now ollama 2>/dev/null || true
  fi

  log "Pulling Ollama models: ${OLLAMA_MODELS[*]}"
  for model in "${OLLAMA_MODELS[@]}"; do
    run_as_invoking_user ollama pull "${model}"
  done
  add_report_note "Ollama models available: ${OLLAMA_MODELS[*]}."
}

install_whisper_cpp_dependency() {
  if [[ "${SKIP_WHISPER}" -eq 1 ]]; then
    log "Skipping whisper.cpp."
    add_report_note "whisper.cpp installation skipped."
    return
  fi

  log "Building whisper.cpp."
  rm -rf "${BUILD_DIR}/whisper.cpp"
  git clone --depth 1 --branch "${WHISPER_CPP_REF}" https://github.com/ggml-org/whisper.cpp.git "${BUILD_DIR}/whisper.cpp"
  cmake -S "${BUILD_DIR}/whisper.cpp" -B "${BUILD_DIR}/whisper.cpp/build"
  cmake --build "${BUILD_DIR}/whisper.cpp/build" -j"$(nproc)"

  local whisper_bin="${BUILD_DIR}/whisper.cpp/build/bin/whisper-cli"
  [[ -x "${whisper_bin}" ]] || fail "whisper-cli was not found at ${whisper_bin}"
  install -m 0755 "${whisper_bin}" "${INSTALL_ROOT}/bin/whisper-cli"
  mkdir -p "${INSTALL_ROOT}/lib"
  find \
    "${BUILD_DIR}/whisper.cpp/build/src" \
    "${BUILD_DIR}/whisper.cpp/build/ggml/src" \
    -maxdepth 1 \
    \( -name 'libwhisper.so*' -o -name 'libggml*.so*' \) \
    -exec cp -a {} "${INSTALL_ROOT}/lib/" \;

  log "Downloading Whisper models: ${WHISPER_MODELS[*]}"
  for model in "${WHISPER_MODELS[@]}"; do
    bash "${BUILD_DIR}/whisper.cpp/models/download-ggml-model.sh" "${model}"
    install -m 0644 \
      "${BUILD_DIR}/whisper.cpp/models/ggml-${model}.bin" \
      "${INSTALL_ROOT}/models/whisper/ggml-${model}.bin"
  done
  add_report_note "whisper.cpp installed with models: ${WHISPER_MODELS[*]}."
}

piper_asset_name() {
  case "$(uname -m)" in
    x86_64|amd64)
      printf 'piper_amd64.tar.gz'
      ;;
    aarch64|arm64)
      printf 'piper_arm64.tar.gz'
      ;;
    *)
      fail "Unsupported CPU architecture for automatic Piper install: $(uname -m)"
      ;;
  esac
}

install_piper_dependency() {
  if [[ "${SKIP_PIPER}" -eq 1 ]]; then
    log "Skipping Piper."
    add_report_note "Piper installation skipped."
    return
  fi

  local asset piper_url
  asset="$(piper_asset_name)"
  piper_url="https://github.com/rhasspy/piper/releases/download/v${PIPER_VERSION}/${asset}"

  log "Installing Piper ${PIPER_VERSION}."
  rm -rf "${BUILD_DIR}/piper" "${BUILD_DIR}/${asset}"
  wget -O "${BUILD_DIR}/${asset}" "${piper_url}"
  mkdir -p "${BUILD_DIR}/piper"
  tar -xzf "${BUILD_DIR}/${asset}" -C "${BUILD_DIR}/piper" --strip-components=1

  [[ -x "${BUILD_DIR}/piper/piper" ]] || fail "Piper binary was not found after extracting ${asset}"
  rm -rf "${INSTALL_ROOT}/piper"
  cp -a "${BUILD_DIR}/piper" "${INSTALL_ROOT}/piper"
  cat > "${INSTALL_ROOT}/bin/piper" <<EOF
#!/usr/bin/env bash
set -euo pipefail
PIPER_DIR="${INSTALL_ROOT}/piper"
export LD_LIBRARY_PATH="\${PIPER_DIR}:\${LD_LIBRARY_PATH:-}"
exec "\${PIPER_DIR}/piper" "\$@"
EOF
  chmod 0755 "${INSTALL_ROOT}/bin/piper"

  log "Downloading Piper voice ${PIPER_VOICE}."
  wget -O "${INSTALL_ROOT}/models/piper/${PIPER_VOICE}.onnx" \
    "${PIPER_VOICE_BASE_URL}/${PIPER_VOICE}.onnx"
  wget -O "${INSTALL_ROOT}/models/piper/${PIPER_VOICE}.onnx.json" \
    "${PIPER_VOICE_BASE_URL}/${PIPER_VOICE}.onnx.json"
  add_report_note "Piper ${PIPER_VERSION} installed with voice ${PIPER_VOICE}."
}

run_dependency_installer() {
  if [[ "${RUN_DEPENDENCIES}" -eq 0 ]]; then
    log "Skipping external dependency installation."
    add_report_note "External dependency installation skipped."
    return
  fi

  log "Installing dependencies directly from install.sh."
  install_system_packages
  prepare_dependency_dirs
  install_ollama_dependency
  install_whisper_cpp_dependency
  install_piper_dependency
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

configure_runtime_defaults() {
  log "Configuring always-listening fullscreen defaults."
  "${INSTALL_ROOT}/venv/bin/python" - "${CONFIG_ROOT}/config.yaml" <<'HEY_GHOST_CONFIG_DEFAULTS'
from pathlib import Path
import sys
import yaml

path = Path(sys.argv[1])
with path.open("r", encoding="utf-8") as handle:
    config = yaml.safe_load(handle) or {}

config.setdefault("assistant", {})["mode"] = "always_listening"
config.setdefault("assistant", {})["max_response_words"] = 50
config.setdefault("llm", {})["num_ctx"] = 1024
config.setdefault("llm", {})["num_predict"] = 64
config.setdefault("wake_word", {})["engine"] = "always_on"
config.setdefault("wake_word", {})["session_mode"] = "always_listening"
config.setdefault("gui", {})["fullscreen"] = True
config.setdefault("gui", {})["diagnostics_default"] = True
config.setdefault("audio", {})["sample_rate"] = 48000
config.setdefault("audio", {})["vad_aggressiveness"] = 2
config.setdefault("audio", {})["silence_timeout_ms"] = 700
config.setdefault("audio", {})["min_speech_ms"] = 90

with path.open("w", encoding="utf-8") as handle:
    yaml.safe_dump(config, handle, sort_keys=False)
HEY_GHOST_CONFIG_DEFAULTS
  add_report_note "Config set to always listening, fullscreen diagnostic GUI, and laptop-friendly speech detection by default."
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
  configure_runtime_defaults

  mkdir -p \
    "${INSTALL_ROOT}/bin" \
    "${INSTALL_ROOT}/lib" \
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
  if systemctl is-active --quiet hey-ghost.service 2>/dev/null; then
    printf '[%s] hey-ghost.service is active; opening GUI monitor only\n' "\$(date -Is)"
    HEY_GHOST_CONFIG="\${SOURCE_CONFIG}" exec "${WRAPPER_PATH}" debug-window
  fi
  printf '[%s] hey-ghost.service is not active; starting desktop assistant\n' "\$(date -Is)"
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
  PYTHONWARNINGS="ignore:pkg_resources is deprecated as an API:UserWarning" \
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

print_install_report() {
  local service_state="not checked"
  if systemctl is-active --quiet hey-ghost.service; then
    service_state="running"
  else
    service_state="not running"
  fi

  cat <<EOF

HeyGhost install report
=======================

Result:
  Install completed successfully.
  Post-install checks passed.
  Service status: ${service_state}

Installed locations:
  App files:        ${INSTALL_ROOT}
  Config file:      ${CONFIG_ROOT}/config.yaml
  Logs:             ${LOG_DIR}
  Command:          ${WRAPPER_PATH}
  Desktop launcher: ${DESKTOP_WRAPPER_PATH}
  Systemd service:  hey-ghost.service

Installed runtime pieces:
EOF

  for note in "${REPORT_NOTES[@]}"; do
    printf '  - %s\n' "${note}"
  done

  cat <<EOF

Verified checks:
  - Required runtime files exist
  - Python imports load
  - Config file loads
  - HeyGhost Python tests passed or were intentionally skipped
  - Ollama responds
  - Piper binary runs
  - whisper.cpp binary runs
  - hey-ghost.service starts

How to use HeyGhost:
  Start service:      heyghost start
  Stop service:       heyghost stop
  Service status:     heyghost status
  Open GUI:           double-click the HeyGhost desktop icon
  Trigger listening:  heyghost trigger
  Test Ollama:        heyghost test-ollama
  Test speech:        heyghost test-tts
  Watch logs:         journalctl -u hey-ghost.service -f

Beginner notes:
  - Double-click the desktop icon to open the GhostWave GUI.
  - Click the GUI window or press Space to start a listening session.
  - If audio devices are wrong, edit ${CONFIG_ROOT}/config.yaml.
  - GUI launch logs are under ~/.local/state/heyghost/.

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
print_install_report
