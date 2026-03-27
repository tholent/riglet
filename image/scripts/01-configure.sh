#!/usr/bin/env bash
set -euo pipefail

RIGLET_APP=/opt/riglet/app
RIGLET_VENV=/opt/riglet/venv
RIGLET_CONF=/etc/riglet
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FILES_DIR="$(dirname "$SCRIPT_DIR")/files"

# 1. Create ham user if not exists
id -u ham &>/dev/null || useradd -m -s /bin/bash -G dialout,audio,plugdev ham

# 2. Create directories
mkdir -p "$RIGLET_APP" "$RIGLET_CONF"

# 3. Copy app source
cp -r "$SCRIPT_DIR/../../../server" "$RIGLET_APP/server"

# 4. Copy static UI build (if present)
if [ -d "$SCRIPT_DIR/../../../ui/build" ]; then
    cp -r "$SCRIPT_DIR/../../../ui/build" "$RIGLET_APP/static"
fi

# 5. Create venv and install
python3 -m venv "$RIGLET_VENV"
"$RIGLET_VENV/bin/pip" install --quiet -e "$RIGLET_APP/server"

# 6. Install systemd units
cp "$FILES_DIR/riglet.service" /etc/systemd/system/
cp "$FILES_DIR/rigctld@.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable riglet.service
systemctl enable avahi-daemon.service

# 7. Install default config (only if not already present)
if [ ! -f "$RIGLET_CONF/config.yaml" ]; then
    cp "$FILES_DIR/config.yaml.default" "$RIGLET_CONF/config.yaml"
fi

# 8. SSH hardening
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config

# 9. Permissions
chown -R ham:ham /opt/riglet "$RIGLET_CONF"
