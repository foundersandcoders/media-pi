#!/usr/bin/env bash
#
# &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
# ENTIRE FILE NEW — scaffold, remove &/! markers on implementation (Stage 2)
# &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
#
# install-netcheck.sh — install the Wi-Fi/Tailscale watchdog on the Pi (run once).
# Must run on the Pi (Linux + NetworkManager + systemd), as a sudo-capable user.
#
# STUB: every step is printed, not executed ("would: ..."), so this is safe to run
# on the dev Mac to review the flow. Stage 2 replaces each `step` with the real cmd.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
cd "$REPO_ROOT"

step() { echo "install-netcheck: would: $*"; } # STUB executor — prints instead of running

# should refuse to run anywhere but Linux (NetworkManager/systemd/iw are Linux-only)
# SEAM: uname / OSTYPE guard
if [[ "$OSTYPE" == "darwin"* ]]; then
  echo "install-netcheck: STUB run on macOS — printing steps only, installing nothing." >&2
fi

# 1. Disable Wi-Fi power-save persistently (the root-cause fix)
# should copy the drop-in into NetworkManager's conf.d and reload
# SEAM: cp -> /etc/NetworkManager/conf.d/ ; systemctl reload NetworkManager
step "sudo cp deploy/wifi-powersave-off.conf /etc/NetworkManager/conf.d/"
step "sudo systemctl reload NetworkManager"

# 2. Apply power-save off to the live radio now (don't wait for a reconnect)
# should set it immediately so the current session is protected too
# SEAM: iw dev wlan0 set power_save off
step "sudo iw dev wlan0 set power_save off"

# 3. Install the watchdog timer + service
# should copy both units, reload systemd, and enable the timer at boot
# SEAM: cp -> /etc/systemd/system/ ; systemctl daemon-reload ; enable --now
step "sudo cp deploy/media-pi-netcheck.service deploy/media-pi-netcheck.timer /etc/systemd/system/"
step "sudo systemctl daemon-reload"
step "sudo systemctl enable --now media-pi-netcheck.timer"

# 4. Verify
# should confirm power_save is off and the timer is active/enabled
# SEAM: iw ... get power_save ; systemctl status media-pi-netcheck.timer
step "iw dev wlan0 get power_save        # expect: Power save: off"
step "systemctl list-timers media-pi-netcheck.timer"
step "journalctl -u media-pi-netcheck -n 20 --no-pager"

echo "install-netcheck: STUB complete — no changes made."
