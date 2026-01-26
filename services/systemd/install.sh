#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="isponsorblocktv"
INSTALL_DIR="/opt/isponsorblocktv"
DATA_DIR="/var/lib/isponsorblocktv"
USER_NAME="isponsorblocktv"
GROUP_NAME="isponsorblocktv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root." >&2
  exit 1
fi

if [[ ! -d "$INSTALL_DIR" ]]; then
  echo "Expected app directory at $INSTALL_DIR" >&2
  exit 1
fi

if ! id "$USER_NAME" >/dev/null 2>&1; then
  useradd --system --home "$DATA_DIR" --create-home "$USER_NAME"
fi

install -d -o "$USER_NAME" -g "$GROUP_NAME" "$DATA_DIR"

SERVICE_FILE="${SCRIPT_DIR}/isponsorblocktv.service"
if [[ ! -f "$SERVICE_FILE" ]]; then
  echo "Missing $SERVICE_FILE" >&2
  exit 1
fi

cp "$SERVICE_FILE" "/etc/systemd/system/${SERVICE_NAME}.service"

systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"

install -d /usr/local/bin
cat <<EOT >/usr/local/bin/iSponsorBlockTV
#!/usr/bin/env bash
export iSPBTV_data_dir="${DATA_DIR}"

set +e
"${INSTALL_DIR}/venv/bin/iSponsorBlockTV" "\$@"
status=\$?
set -e

case "\${1:-}" in
  setup|setup-cli)
    systemctl restart "${SERVICE_NAME}" >/dev/null 2>&1 || true
    ;;
esac

exit \$status
EOT
chmod +x /usr/local/bin/iSponsorBlockTV
ln -sf /usr/local/bin/iSponsorBlockTV /usr/bin/iSponsorBlockTV

cat <<EOT >/etc/profile.d/isponsorblocktv.sh
export iSPBTV_data_dir="${DATA_DIR}"
EOT
if ! grep -q '^iSPBTV_data_dir=' /etc/environment 2>/dev/null; then
  cat <<EOT >>/etc/environment
iSPBTV_data_dir=${DATA_DIR}
EOT
fi

echo "Service installed and started: $SERVICE_NAME"
