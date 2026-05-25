#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="${HEY_GHOST_INSTALL_ROOT:-/opt/hey-ghost}"
WHISPER_CPP_REF="${WHISPER_CPP_REF:-master}"
WHISPER_MODELS=("tiny.en" "base.en")
OLLAMA_MODELS=("qwen2.5:0.5b" "nomic-embed-text")
PIPER_VERSION="${PIPER_VERSION:-1.2.0}"
PIPER_VOICE="${PIPER_VOICE:-en_US-lessac-medium}"
PIPER_VOICE_BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
BUILD_DIR="${HEY_GHOST_BUILD_DIR:-/tmp/heyghost-deps}"
SKIP_OLLAMA=0
SKIP_WHISPER=0
SKIP_PIPER=0

usage() {
  cat <<EOF
Usage: sudo ./scripts/install_dependencies.sh [options]

Installs external HeyGhost dependencies into ${INSTALL_ROOT}.

Options:
  --install-root PATH       Install root, default: /opt/hey-ghost
  --ollama-model MODEL      Pull an additional Ollama model. Can be repeated.
  --whisper-model MODEL     Download a whisper.cpp model. Can be repeated.
                            Defaults: tiny.en and base.en
  --piper-version VERSION   Piper release version, default: ${PIPER_VERSION}
  --piper-voice VOICE       Piper voice name, default: ${PIPER_VOICE}
  --skip-ollama             Do not install Ollama or pull Ollama models
  --skip-whisper            Do not build/install whisper.cpp
  --skip-piper              Do not install Piper or voice model
  -h, --help                Show this help

Examples:
  sudo ./scripts/install_dependencies.sh
  sudo ./scripts/install_dependencies.sh --ollama-model llama3.2:1b
  sudo HEY_GHOST_INSTALL_ROOT=/srv/heyghost ./scripts/install_dependencies.sh
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-root)
      INSTALL_ROOT="$2"
      shift 2
      ;;
    --ollama-model)
      OLLAMA_MODELS+=("$2")
      shift 2
      ;;
    --whisper-model)
      WHISPER_MODELS+=("$2")
      shift 2
      ;;
    --piper-version)
      PIPER_VERSION="$2"
      shift 2
      ;;
    --piper-voice)
      PIPER_VOICE="$2"
      shift 2
      ;;
    --skip-ollama)
      SKIP_OLLAMA=1
      shift
      ;;
    --skip-whisper)
      SKIP_WHISPER=1
      shift
      ;;
    --skip-piper)
      SKIP_PIPER=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this script with sudo because it installs packages and writes to ${INSTALL_ROOT}." >&2
    exit 1
  fi
}

log() {
  printf '\n[heyghost-deps] %s\n' "$*"
}

run_as_invoking_user() {
  if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    sudo -u "${SUDO_USER}" env HOME="$(getent passwd "${SUDO_USER}" | cut -d: -f6)" "$@"
  else
    "$@"
  fi
}

install_system_packages() {
  log "Installing system packages"
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
    portaudio19-dev \
    ffmpeg \
    alsa-utils
}

prepare_dirs() {
  log "Preparing ${INSTALL_ROOT}"
  mkdir -p \
    "${INSTALL_ROOT}/bin" \
    "${INSTALL_ROOT}/models/whisper" \
    "${INSTALL_ROOT}/models/piper" \
    "${INSTALL_ROOT}/knowledge" \
    "${INSTALL_ROOT}/shared" \
    "${BUILD_DIR}"
}

install_ollama() {
  if [[ "${SKIP_OLLAMA}" -eq 1 ]]; then
    log "Skipping Ollama"
    return
  fi

  if ! command -v ollama >/dev/null 2>&1; then
    log "Installing Ollama"
    curl -fsSL https://ollama.com/install.sh | sh
  else
    log "Ollama already installed"
  fi

  if command -v systemctl >/dev/null 2>&1; then
    systemctl enable --now ollama 2>/dev/null || true
  fi

  log "Pulling Ollama models"
  for model in "${OLLAMA_MODELS[@]}"; do
    run_as_invoking_user ollama pull "${model}"
  done
}

install_whisper_cpp() {
  if [[ "${SKIP_WHISPER}" -eq 1 ]]; then
    log "Skipping whisper.cpp"
    return
  fi

  log "Building whisper.cpp"
  rm -rf "${BUILD_DIR}/whisper.cpp"
  git clone --depth 1 --branch "${WHISPER_CPP_REF}" https://github.com/ggml-org/whisper.cpp.git "${BUILD_DIR}/whisper.cpp"
  cmake -S "${BUILD_DIR}/whisper.cpp" -B "${BUILD_DIR}/whisper.cpp/build"
  cmake --build "${BUILD_DIR}/whisper.cpp/build" -j"$(nproc)"

  local whisper_bin="${BUILD_DIR}/whisper.cpp/build/bin/whisper-cli"
  if [[ ! -x "${whisper_bin}" ]]; then
    echo "whisper-cli was not found at ${whisper_bin}" >&2
    exit 1
  fi

  install -m 0755 "${whisper_bin}" "${INSTALL_ROOT}/bin/whisper-cli"

  log "Downloading Whisper models"
  for model in "${WHISPER_MODELS[@]}"; do
    bash "${BUILD_DIR}/whisper.cpp/models/download-ggml-model.sh" "${model}"
    install -m 0644 \
      "${BUILD_DIR}/whisper.cpp/models/ggml-${model}.bin" \
      "${INSTALL_ROOT}/models/whisper/ggml-${model}.bin"
  done
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
      echo "Unsupported CPU architecture for automatic Piper install: $(uname -m)" >&2
      echo "Install Piper manually and place the binary at ${INSTALL_ROOT}/bin/piper" >&2
      exit 1
      ;;
  esac
}

install_piper() {
  if [[ "${SKIP_PIPER}" -eq 1 ]]; then
    log "Skipping Piper"
    return
  fi

  local asset
  asset="$(piper_asset_name)"
  local piper_url="https://github.com/rhasspy/piper/releases/download/v${PIPER_VERSION}/${asset}"

  log "Installing Piper ${PIPER_VERSION}"
  rm -rf "${BUILD_DIR}/piper" "${BUILD_DIR}/${asset}"
  wget -O "${BUILD_DIR}/${asset}" "${piper_url}"
  mkdir -p "${BUILD_DIR}/piper"
  tar -xzf "${BUILD_DIR}/${asset}" -C "${BUILD_DIR}/piper" --strip-components=1

  if [[ ! -x "${BUILD_DIR}/piper/piper" ]]; then
    echo "Piper binary was not found after extracting ${asset}" >&2
    exit 1
  fi

  install -m 0755 "${BUILD_DIR}/piper/piper" "${INSTALL_ROOT}/bin/piper"

  log "Downloading Piper voice ${PIPER_VOICE}"
  wget -O "${INSTALL_ROOT}/models/piper/${PIPER_VOICE}.onnx" \
    "${PIPER_VOICE_BASE_URL}/${PIPER_VOICE}.onnx"
  wget -O "${INSTALL_ROOT}/models/piper/${PIPER_VOICE}.onnx.json" \
    "${PIPER_VOICE_BASE_URL}/${PIPER_VOICE}.onnx.json"
}

print_summary() {
  cat <<EOF

HeyGhost dependency installation complete.

Installed paths:
  whisper.cpp: ${INSTALL_ROOT}/bin/whisper-cli
  Whisper models: ${INSTALL_ROOT}/models/whisper
  Piper: ${INSTALL_ROOT}/bin/piper
  Piper voice: ${INSTALL_ROOT}/models/piper/${PIPER_VOICE}.onnx

Recommended next steps:
  cd /path/to/HeyGhost
  sudo ./install.sh
  heyghost test-ollama
  heyghost test-tts
  heyghost start
  heyghost trigger

If your microphone or speaker does not work, edit:
  /etc/hey-ghost/config.yaml

EOF
}

require_root
install_system_packages
prepare_dirs
install_ollama
install_whisper_cpp
install_piper
print_summary
