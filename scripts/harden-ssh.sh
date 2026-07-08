#!/bin/bash
set -euo pipefail

if ! grep -q "^deploy:" /etc/passwd; then
  echo "MISSING deploy user — aborting, do not lock out root yet" >&2
  exit 1
fi

if [ ! -s /home/deploy/.ssh/authorized_keys ]; then
  echo "MISSING /home/deploy/.ssh/authorized_keys — aborting, do not lock out root yet" >&2
  exit 1
fi

echo "deploy user and authorized_keys OK, proceeding"

sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config

sshd -t
systemctl restart ssh
echo "sshd config valid, restarted. Root SSH login and password auth are now disabled."
