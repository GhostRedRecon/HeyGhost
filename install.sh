#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_ROOT="${HEY_GHOST_INSTALL_ROOT:-/opt/hey-ghost}"
CONFIG_ROOT="${HEY_GHOST_CONFIG_ROOT:-/etc/hey-ghost}"
SERVICE_PATH="${HEY_GHOST_SERVICE_PATH:-/etc/systemd/system/hey-ghost.service}"
WRAPPER_PATH="${HEY_GHOST_WRAPPER_PATH:-/usr/local/bin/heyghost}"
LOG_DIR="${HEY_GHOST_LOG_DIR:-/var/log/hey-ghost}"
SERVICE_USER="${HEY_GHOST_SERVICE_USER:-heyghost}"
SERVICE_GROUP="${HEY_GHOST_SERVICE_GROUP:-${SERVICE_USER}}"

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "Run install.sh as root."
    exit 1
  fi
}

install_packages() {
  apt-get update
  apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    build-essential \
    portaudio19-dev \
    ffmpeg \
    alsa-utils
}

create_service_user() {
  if ! getent group "${SERVICE_GROUP}" >/dev/null 2>&1; then
    groupadd --system "${SERVICE_GROUP}"
  fi

  if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
    useradd --system --home "${INSTALL_ROOT}" --shell /usr/sbin/nologin --gid "${SERVICE_GROUP}" "${SERVICE_USER}"
  fi

  usermod -aG audio "${SERVICE_USER}" || true
}

install_files() {
  mkdir -p "${INSTALL_ROOT}" "${CONFIG_ROOT}" "${LOG_DIR}"
  rm -rf \
    "${INSTALL_ROOT}/heyghost" \
    "${INSTALL_ROOT}/heyghost.py" \
    "${INSTALL_ROOT}/tests" \
    "${INSTALL_ROOT}/scripts" \
    "${INSTALL_ROOT}/systemd" \
    "${INSTALL_ROOT}/README.md" \
    "${INSTALL_ROOT}/MIGRATION_NOTES.md" \
    "${INSTALL_ROOT}/PROJECT_CONTEXT.md" \
    "${INSTALL_ROOT}/requirements.txt" \
    "${INSTALL_ROOT}/config.example.yaml" \
    "${INSTALL_ROOT}/github.txt"

  cp -a "${PROJECT_ROOT}/heyghost" "${INSTALL_ROOT}/heyghost"
  cp -a "${PROJECT_ROOT}/heyghost.py" "${INSTALL_ROOT}/heyghost.py"
  cp -a "${PROJECT_ROOT}/requirements.txt" "${INSTALL_ROOT}/requirements.txt"
  cp -a "${PROJECT_ROOT}/README.md" "${INSTALL_ROOT}/README.md"
  cp -a "${PROJECT_ROOT}/MIGRATION_NOTES.md" "${INSTALL_ROOT}/MIGRATION_NOTES.md"
  cp -a "${PROJECT_ROOT}/PROJECT_CONTEXT.md" "${INSTALL_ROOT}/PROJECT_CONTEXT.md"
  cp -a "${PROJECT_ROOT}/config.example.yaml" "${INSTALL_ROOT}/config.example.yaml"
  cp -a "${PROJECT_ROOT}/github.txt" "${INSTALL_ROOT}/github.txt" 2>/dev/null || true

  if [[ ! -f "${CONFIG_ROOT}/config.yaml" ]]; then
    cp "${PROJECT_ROOT}/config.example.yaml" "${CONFIG_ROOT}/config.yaml"
  else
    echo "Keeping existing ${CONFIG_ROOT}/config.yaml"
  fi

  python3 -m venv "${INSTALL_ROOT}/venv"
  "${INSTALL_ROOT}/venv/bin/pip" install --upgrade pip
  "${INSTALL_ROOT}/venv/bin/pip" install -r "${PROJECT_ROOT}/requirements.txt"

  mkdir -p \
    "${INSTALL_ROOT}/bin" \
    "${INSTALL_ROOT}/models/whisper" \
    "${INSTALL_ROOT}/models/piper" \
    "${INSTALL_ROOT}/knowledge" \
    "${INSTALL_ROOT}/shared"
  chown -R "${SERVICE_USER}:${SERVICE_GROUP}" \
    "${INSTALL_ROOT}" \
    "${LOG_DIR}"
}

install_wrapper() {
  cat > "${WRAPPER_PATH}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export HEY_GHOST_INSTALL_ROOT="\${HEY_GHOST_INSTALL_ROOT:-${INSTALL_ROOT}}"
export HEY_GHOST_CONFIG_ROOT="\${HEY_GHOST_CONFIG_ROOT:-${CONFIG_ROOT}}"
export HEY_GHOST_LOG_DIR="\${HEY_GHOST_LOG_DIR:-${LOG_DIR}}"
exec "${INSTALL_ROOT}/venv/bin/python" "${INSTALL_ROOT}/heyghost.py" --config "\${HEY_GHOST_CONFIG:-${CONFIG_ROOT}/config.yaml}" "\$@"
EOF
  chmod +x "${WRAPPER_PATH}"
}

install_service() {
  cat > "${SERVICE_PATH}" <<EOF
[Unit]
Description=HeyGhost Local Voice Assistant
After=network.target sound.target
Wants=network.target

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
  systemctl daemon-reload
  systemctl enable hey-ghost.service
}

print_next_steps() {
  cat <<EOF
Install complete.

Next steps:
1. Review ${CONFIG_ROOT}/config.yaml and set audio devices if needed.
2. Place whisper.cpp binary at ${INSTALL_ROOT}/bin/whisper-cli
3. Place whisper models under ${INSTALL_ROOT}/models/whisper
4. Place Piper binary at ${INSTALL_ROOT}/bin/piper
5. Place Piper voice model at ${INSTALL_ROOT}/models/piper/en_US-lessac-medium.onnx
6. Install and start Ollama, then run: ollama pull qwen2.5:0.5b
7. For RAG support, run: ollama pull nomic-embed-text
8. Start the service with: heyghost start

Development wake trigger:
  heyghost trigger
EOF
}

require_root
install_packages
create_service_user
install_files
install_wrapper
install_service
enable_service
print_next_steps
