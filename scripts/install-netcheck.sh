#!/usr/bin/env bash
#
# install-netcheck.sh — install the Wi-Fi/Tailscale watchdog on the Pi (run once).
# Must run on the Pi (Linux + NetworkManager + systemd), as a sudo-capable user.
# Idempotent: safe to re-run after pulling changes.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
cd "$REPO_ROOT"

if [[ "$OSTYPE" != linux* ]]; then
  echo "install-netcheck: this installer only runs on the Pi (Linux). Aborting." >&2
  exit 1
fi

WLAN_IF="${WLAN_IF:-wlan0}"

echo "install-netcheck: 1/4 disabling Wi-Fi power-save (NetworkManager drop-in)"
sudo cp deploy/wifi-powersave-off.conf /etc/NetworkManager/conf.d/
sudo systemctl reload NetworkManager

echo "install-netcheck: 2/4 applying power-save off to $WLAN_IF now"
sudo iw dev "$WLAN_IF" set power_save off ||
  echo "  (couldn't set live now; the conf.d drop-in applies on next reconnect)" >&2

echo "install-netcheck: 3/4 installing watchdog timer + service"
sudo cp deploy/media-pi-netcheck.service deploy/media-pi-netcheck.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now media-pi-netcheck.timer

echo "install-netcheck: 4/4 verifying"
iw dev "$WLAN_IF" get power_save || true
systemctl list-timers media-pi-netcheck.timer --no-pager || true
echo "install-netcheck: done. Follow runs with: journalctl -u media-pi-netcheck -f"
