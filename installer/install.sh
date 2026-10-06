#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Run installer as root."
  exit 1
fi

PREFIX=${NVM_PREFIX:-/opt/nvm}
DATA=${NVM_DATA_DIR:-/var/lib/nvm}
SERVICE_USER=${NVM_USER:-${SUDO_USER:-root}}
SERVICE_GROUP=${NVM_GROUP:-${SERVICE_USER}}

python3 -m venv "$PREFIX/venv"
"$PREFIX/venv/bin/pip" install --upgrade pip
"$PREFIX/venv/bin/pip" install "$PWD"

mkdir -p "$DATA"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$PREFIX" "$DATA" 2>/dev/null || true

install -m 0755 "$PWD/installer/nvm.initd" /etc/init.d/nvm
rc-update add nvm default 2>/dev/null || true

echo "NVM installed at $PREFIX"
echo "Data directory: $DATA"
echo "Set NVM_HOST=0.0.0.0 for LAN/ESP32 access."
echo "Set NVM_ADMIN_TOKEN before provisioning ESP32 devices."
echo "Start with: rc-service nvm start"
