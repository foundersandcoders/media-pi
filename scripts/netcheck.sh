#!/usr/bin/env bash
#
# &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
# ENTIRE FILE NEW — scaffold, remove &/! markers on implementation (Stage 2)
# &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
#
# netcheck.sh — Wi-Fi / Tailscale reachability watchdog for the unattended Pi.
#
# Root cause it guards: wlan0 power-save parks the radio while idle, the tailnet
# link goes stale, and `ssh admin@media-pi` times out on port 22. Disabling
# power-save (deploy/wifi-powersave-off.conf) is the real fix; this is the
# self-healing safety net, and its 5-min traffic also keeps the radio warm.
#
# Runs as a systemd oneshot every 5 min — see deploy/media-pi-netcheck.timer.
#
# Contract — the shape every check/heal shares (declared ONCE, referenced below):
#   check_*  -> return 0 = healthy, non-zero = unhealthy; logs a human status line
#   heal_*   -> perform ONE recovery action, log it, return 0 once attempted
#   escalation order: power-save off  ->  restart tailscaled  ->  bounce wlan0
#
# STUB: every body returns FAKE "healthy" so the skeleton runs end-to-end on any
# box (incl. the dev Mac, which has no wlan0/iw/tailscale) and mutates nothing.
# Set NETCHECK_DEMO=unhealthy to force the failure path and watch self-heal fire.

set -euo pipefail

# ---- config (env-overridable, mirrors record.sh) --------------------------
WLAN_IF="${WLAN_IF:-wlan0}"
SSH_PORT="${SSH_PORT:-22}"
TS_PEER="${TS_PEER:-}"    # tailnet peer to ping; empty = pick any active peer
DEMO="${NETCHECK_DEMO:-}" # "unhealthy" forces checks to fail (stub demo only)

log() {
  # timestamped line to stdout; systemd/journald captures it
  echo "netcheck: $(date '+%H:%M:%S') $*"
}

# ---- checks (leaf; each SEAM to a system tool) ----------------------------

check_powersave() {
  # out: 0 healthy / 1 needs-fix
  # SEAM: iw dev "$WLAN_IF" get power_save
  # should report healthy when power_save is "off"
  # should report unhealthy (1) when power_save is "on" (the drift we guard against)
  log "check: $WLAN_IF power_save == off (fake: off)"
  [[ "$DEMO" == "unhealthy" ]] && return 1
  return 0 # fake: healthy
}

check_wlan_link() {
  # out: 0 healthy / 1 down
  # SEAM: ip -4 addr show "$WLAN_IF"  /  nmcli -t device status
  # should report healthy when wlan0 is associated AND holds an IPv4
  # should report unhealthy when there is no carrier or no lease
  log "check: $WLAN_IF associated + has IPv4 (fake: 192.168.10.57)"
  [[ "$DEMO" == "unhealthy" ]] && return 1
  return 0 # fake: healthy
}

check_tailscale_backend() {
  # out: 0 healthy / 1 not-running
  # SEAM: tailscale status --json | jq -r .BackendState
  # should report healthy when BackendState == "Running"
  # should report unhealthy for "Stopped" / "NeedsLogin" / daemon unreachable
  log "check: tailscaled BackendState == Running (fake: Running)"
  [[ "$DEMO" == "unhealthy" ]] && return 1
  return 0 # fake: healthy
}

check_tailscale_peer() {
  # out: 0 healthy / 1 unreachable
  # SEAM: tailscale ping -c 1 "<peer>"  (peer = $TS_PEER, else first active peer)
  # should pick any active peer when TS_PEER is empty
  # should report healthy when a peer answers (direct OR via DERP)
  # should report unhealthy when the ping times out
  local peer="${TS_PEER:-<first-active-peer>}"
  log "check: tailscale ping $peer answers (fake: direct)"
  [[ "$DEMO" == "unhealthy" ]] && return 1
  return 0 # fake: healthy
}

check_ssh_port() {
  # out: 0 healthy / 1 not-listening
  # SEAM: ss -H -ltn "sport = :$SSH_PORT"
  # should report healthy when sshd is LISTENing on $SSH_PORT
  # should report unhealthy when nothing is bound (sshd dead)
  log "check: sshd LISTEN on :$SSH_PORT (fake: listening)"
  [[ "$DEMO" == "unhealthy" ]] && return 1
  return 0 # fake: healthy
}

# ---- heals (escalation; each SEAM to a system mutation) -------------------

heal_powersave() {
  # SEAM: iw dev "$WLAN_IF" set power_save off
  # should force power_save off immediately (belt to the conf.d braces)
  log "heal: iw dev $WLAN_IF set power_save off (fake: no-op)"
  return 0 # fake: attempted
}

heal_tailscale() {
  # SEAM: systemctl restart tailscaled  (then `tailscale up` re-asserts state)
  # should restart the daemon to rebuild the control-plane + WireGuard sessions
  # should be safe to run repeatedly (idempotent)
  log "heal: systemctl restart tailscaled (fake: no-op)"
  return 0 # fake: attempted
}

heal_wlan() {
  # SEAM: nmcli device disconnect "$WLAN_IF" && nmcli device connect "$WLAN_IF"
  # should be the LAST resort — bouncing the link drops every session on it
  # should re-associate + re-lease so the radio comes back clean
  log "heal: bounce $WLAN_IF via nmcli (fake: no-op) [last resort]"
  return 0 # fake: attempted
}

# ---- orchestration --------------------------------------------------------

run_checks() {
  # runs every check; echoes space-separated names of the ones that FAILED ("" = all healthy)
  # check log lines go to stderr so stdout carries only the failed-list
  local failed=""
  check_powersave >&2 || failed+=" powersave"
  check_wlan_link >&2 || failed+=" wlan"
  check_tailscale_backend >&2 || failed+=" ts-backend"
  check_tailscale_peer >&2 || failed+=" ts-peer"
  check_ssh_port >&2 || failed+=" ssh"
  echo "${failed# }"
}

self_heal() {
  # in: space-separated failed-check names   out: none
  # should map each failure class to the cheapest recovery, escalating to wlan bounce
  local failed=" $1 "
  [[ "$failed" == *" powersave "* ]] && heal_powersave
  [[ "$failed" == *" ts-backend "* || "$failed" == *" ts-peer "* ]] && heal_tailscale
  [[ "$failed" == *" wlan "* ]] && heal_wlan
  return 0
}

main() {
  log "=== run start (if=$WLAN_IF demo='${DEMO:-none}') ==="
  local failed
  failed=$(run_checks)
  if [[ -z "$failed" ]]; then
    log "healthy: all checks passed"
    return 0
  fi
  log "UNHEALTHY: [$failed] — starting self-heal"
  self_heal "$failed"
  # re-check once after healing to log the outcome
  failed=$(run_checks)
  if [[ -z "$failed" ]]; then
    log "recovered: healthy after self-heal"
  else
    log "STILL UNHEALTHY after self-heal: [$failed]"
  fi
}

main "$@"
