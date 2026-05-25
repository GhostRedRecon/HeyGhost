#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="${HEY_GHOST_INSTALL_ROOT:-/opt/hey-ghost}"
CONFIG_ROOT="${HEY_GHOST_CONFIG_ROOT:-/etc/hey-ghost}"
SERVICE_PATH="${HEY_GHOST_SERVICE_PATH:-/etc/systemd/system/hey-ghost.service}"
WRAPPER_PATH="${HEY_GHOST_WRAPPER_PATH:-/usr/local/bin/heyghost}"
LOG_DIR="${HEY_GHOST_LOG_DIR:-/var/log/hey-ghost}"
SERVICE_USER="${HEY_GHOST_SERVICE_USER:-heyghost}"
SERVICE_GROUP="${HEY_GHOST_SERVICE_GROUP:-${SERVICE_USER}}"

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "Run uninstall.sh as root."
    exit 1
  fi
}

require_root

systemctl disable --now hey-ghost.service 2>/dev/null || true
rm -f "${SERVICE_PATH}"
systemctl daemon-reload

rm -f "${WRAPPER_PATH}"
rm -rf "${INSTALL_ROOT}"
rm -rf "${CONFIG_ROOT}"
rm -rf "${LOG_DIR}"

if id -u "${SERVICE_USER}" >/dev/null 2>&1; then
  userdel "${SERVICE_USER}" || true
fi

if getent group "${SERVICE_GROUP}" >/dev/null 2>&1; then
  groupdel "${SERVICE_GROUP}" || true
fi

echo "HeyGhost uninstalled."
