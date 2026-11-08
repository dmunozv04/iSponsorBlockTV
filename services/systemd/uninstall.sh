#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="isponsorblocktv"
INSTALL_DIR="/opt/isponsorblocktv"
DATA_DIR="/var/lib/isponsorblocktv"
USER_NAME="isponsorblocktv"
GROUP_NAME="isponsorblocktv"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--purge] [--remove-data] [--remove-install] [--remove-user]
  --purge           Remove the service user/group, ${DATA_DIR}, and ${INSTALL_DIR}.
  --remove-data     Remove ${DATA_DIR}.
  --remove-install  Remove ${INSTALL_DIR}.
  --remove-user     Remove the ${USER_NAME} system user and group.
EOF
}

REMOVE_DATA=0
REMOVE_INSTALL=0
REMOVE_USER=0

for arg in "$@"; do
  case "$arg" in
    --purge)
      REMOVE_DATA=1
      REMOVE_INSTALL=1
      REMOVE_USER=1
      ;;
    --remove-data)
      REMOVE_DATA=1
      ;;
    --remove-install)
      REMOVE_INSTALL=1
      ;;
    --remove-user)
      REMOVE_USER=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root." >&2
  exit 1
fi

if command -v systemctl >/dev/null 2>&1; then
  systemctl disable --now "$SERVICE_NAME" >/dev/null 2>&1 || true
fi

SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
if [[ -f "$SERVICE_FILE" ]]; then
  rm -f "$SERVICE_FILE"
  if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload >/dev/null 2>&1 || true
    systemctl reset-failed "$SERVICE_NAME" >/dev/null 2>&1 || true
  fi
fi

if [[ -f /usr/local/bin/iSponsorBlockTV ]]; then
  rm -f /usr/local/bin/iSponsorBlockTV
fi
if [[ -L /usr/bin/iSponsorBlockTV ]]; then
  rm -f /usr/bin/iSponsorBlockTV
fi

rm -f /etc/profile.d/isponsorblocktv.sh

if [[ -f /etc/environment ]] && grep -q '^iSPBTV_data_dir=' /etc/environment; then
  tmp_file="$(mktemp)"
  sed '/^iSPBTV_data_dir=/d' /etc/environment > "$tmp_file"
  cat "$tmp_file" > /etc/environment
  rm -f "$tmp_file"
fi

if (( REMOVE_USER )); then
  if id "$USER_NAME" >/dev/null 2>&1; then
    userdel "$USER_NAME" || true
  fi
  if getent group "$GROUP_NAME" >/dev/null 2>&1; then
    groupdel "$GROUP_NAME" || true
  fi
fi

if (( REMOVE_DATA )); then
  rm -rf "$DATA_DIR"
fi

if (( REMOVE_INSTALL )); then
  rm -rf "$INSTALL_DIR"
fi

echo "Service uninstalled: $SERVICE_NAME"
