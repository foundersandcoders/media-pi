#!/usr/bin/env bash
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
# Contract — the shape every check/heal shares:
#   check_*  -> return 0 = healthy, non-zero = unhealthy; logs a human status line
#   heal_*   -> perform ONE recovery action, log it, return 0 once attempted
#   escalation order: power-save off  ->  restart tailscaled  ->  bounce wlan0
# A missing tool never aborts the run: the dependent check/heal logs a warning
# and is skipped, so one absent binary can't take the watchdog down.
#
# Env overrides:
#   WLAN_IF          wireless interface (default: autodetect via `iw dev`, else wlan0)
#   SSH_PORT         port to confirm sshd is listening on (default: 22)
#   TS_PEER          tailnet peer to ping (default: first ONLINE peer, else skip)
#   NETCHECK_DRYRUN  =1 to log heals without mutating anything (safe on-Pi test)
#   NETCHECK_DEMO    =unhealthy to force every check to fail (demo the self-heal path)
#   NETCHECK_SETTLE  seconds to wait after a restart/bounce before re-checking (default 4)

set -euo pipefail

WLAN_IF="${WLAN_IF:-}"
SSH_PORT="${SSH_PORT:-22}"
TS_PEER="${TS_PEER:-}"
DRYRUN="${NETCHECK_DRYRUN:-}"
DEMO="${NETCHECK_DEMO:-}"
SETTLE_SECS="${NETCHECK_SETTLE:-4}"
NEEDS_SETTLE=0

log() { echo "netcheck: $(date '+%H:%M:%S') $*"; }
warn() { log "WARN $*"; }
have() { command -v "$1" >/dev/null 2>&1; }

# Resolve the wireless interface once: honour $WLAN_IF, else first `iw dev`, else wlan0.
resolve_wlan_if() {
  if [[ -n "$WLAN_IF" ]]; then return 0; fi
  if have iw; then
    WLAN_IF=$(iw dev 2>/dev/null | awk '/Interface/ {print $2; exit}')
  fi
  WLAN_IF="${WLAN_IF:-wlan0}"
}

# ---- checks (leaf; each SEAM to a system tool) ----------------------------

check_powersave() {
  # SEAM: iw dev "$WLAN_IF" get power_save
  # should report healthy when power_save is "off"
  # should report unhealthy when power_save is "on" (the drift we guard against)
  # should skip (healthy) with a warning when `iw` is unavailable
  [[ "$DEMO" == "unhealthy" ]] && {
    log "check: $WLAN_IF power_save (forced fail)"
    return 1
  }
  if ! have iw; then
    warn "iw not found — skipping power_save check"
    return 0
  fi
  local state
  state=$(iw dev "$WLAN_IF" get power_save 2>/dev/null | awk -F': ' '/Power save/ {print $2; exit}')
  if [[ "$state" == "off" ]]; then
    log "check: $WLAN_IF power_save == off"
    return 0
  fi
  log "check: $WLAN_IF power_save == '${state:-unknown}' (want off)"
  return 1
}

check_wlan_link() {
  # SEAM: ip -4 -o addr show dev "$WLAN_IF" scope global
  # should report healthy when wlan0 holds a global IPv4 (associated + leased)
  # should report unhealthy when there is no carrier or no lease
  [[ "$DEMO" == "unhealthy" ]] && {
    log "check: $WLAN_IF link (forced fail)"
    return 1
  }
  if ! have ip; then
    warn "ip not found — skipping wlan link check"
    return 0
  fi
  local line
  line=$(ip -4 -o addr show dev "$WLAN_IF" scope global 2>/dev/null | grep 'inet ' | head -n1)
  if [[ -n "$line" ]]; then
    log "check: $WLAN_IF associated + has IPv4 ($(awk '{print $4}' <<<"$line"))"
    return 0
  fi
  log "check: $WLAN_IF has no global IPv4 (down or unassociated)"
  return 1
}

check_tailscale_backend() {
  # SEAM: tailscale status --json  -> .BackendState
  # should report healthy when BackendState == "Running"
  # should report unhealthy for "Stopped" / "NeedsLogin" / daemon unreachable
  [[ "$DEMO" == "unhealthy" ]] && {
    log "check: tailscaled backend (forced fail)"
    return 1
  }
  if ! have tailscale; then
    warn "tailscale not found — skipping backend check"
    return 0
  fi
  local state
  state=$(tailscale status --json 2>/dev/null |
    grep -o '"BackendState"[[:space:]]*:[[:space:]]*"[^"]*"' |
    head -n1 | sed 's/.*"\([^"]*\)"$/\1/')
  if [[ "$state" == "Running" ]]; then
    log "check: tailscaled BackendState == Running"
    return 0
  fi
  log "check: tailscaled BackendState == '${state:-unreachable}' (want Running)"
  return 1
}

# First tailnet peer that is neither self nor offline (hostname column), else empty.
ts_pick_online_peer() {
  local self
  self=$(tailscale ip -4 2>/dev/null | head -n1)
  tailscale status 2>/dev/null |
    awk -v self="$self" '$1 ~ /^100\./ && $1 != self && $0 !~ /offline/ {print $2; exit}'
}

check_tailscale_peer() {
  # SEAM: tailscale ping -c 1 --until-direct=false --timeout 5s "<peer>"
  # should ping $TS_PEER when set, else the first ONLINE peer from `tailscale status`
  # should report healthy when the peer answers (direct OR via DERP)
  # should skip (healthy) when no peer is online — nothing to test, don't false-alarm
  [[ "$DEMO" == "unhealthy" ]] && {
    log "check: tailscale peer (forced fail)"
    return 1
  }
  if ! have tailscale; then
    warn "tailscale not found — skipping peer check"
    return 0
  fi
  local peer="$TS_PEER"
  [[ -z "$peer" ]] && peer=$(ts_pick_online_peer)
  if [[ -z "$peer" ]]; then
    log "check: no online tailnet peer to ping — skipping"
    return 0
  fi
  if tailscale ping -c 1 --until-direct=false --timeout 5s "$peer" >/dev/null 2>&1; then
    log "check: tailscale ping $peer answered"
    return 0
  fi
  log "check: tailscale ping $peer timed out"
  return 1
}

check_ssh_port() {
  # SEAM: ss -H -ltn "sport = :$SSH_PORT"
  # should report healthy when sshd is LISTENing on $SSH_PORT
  # should report unhealthy when nothing is bound (sshd dead)
  [[ "$DEMO" == "unhealthy" ]] && {
    log "check: sshd :$SSH_PORT (forced fail)"
    return 1
  }
  if ! have ss; then
    warn "ss not found — skipping ssh port check"
    return 0
  fi
  if ss -H -ltn "sport = :$SSH_PORT" 2>/dev/null | grep -q .; then
    log "check: sshd LISTEN on :$SSH_PORT"
    return 0
  fi
  log "check: nothing LISTENing on :$SSH_PORT"
  return 1
}

# ---- heals (escalation; each SEAM to a system mutation) -------------------

# Run a privileged command, or just log it under NETCHECK_DRYRUN.
do_heal() {
  if [[ -n "$DRYRUN" ]]; then
    log "  dryrun: would run: $*"
    return 0
  fi
  "$@"
}

heal_powersave() {
  # SEAM: iw dev "$WLAN_IF" set power_save off
  # should force power_save off immediately (belt to the conf.d braces)
  log "heal: $WLAN_IF power_save off"
  if have iw; then
    do_heal iw dev "$WLAN_IF" set power_save off || warn "iw set power_save failed"
  else
    warn "iw not found — cannot heal power_save"
  fi
}

heal_tailscale() {
  # SEAM: systemctl restart tailscaled (reconnects from /var/lib/tailscale/tailscaled.state)
  # should restart the daemon to rebuild the control-plane + WireGuard sessions
  # should be idempotent; no `tailscale up` — the saved auth state reconnects on its own
  log "heal: restart tailscaled"
  if have systemctl; then
    do_heal systemctl restart tailscaled || warn "systemctl restart tailscaled failed"
    NEEDS_SETTLE=1
  else
    warn "systemctl not found — cannot restart tailscaled"
  fi
}

heal_wlan() {
  # SEAM: nmcli device disconnect/connect "$WLAN_IF"
  # should be the LAST resort — bouncing the link drops every session on it
  # should re-associate + re-lease so the radio comes back clean
  log "heal: bounce $WLAN_IF [last resort]"
  if have nmcli; then
    do_heal nmcli device disconnect "$WLAN_IF" || warn "nmcli disconnect failed"
    do_heal nmcli device connect "$WLAN_IF" || warn "nmcli connect failed"
    NEEDS_SETTLE=1
  else
    warn "nmcli not found — cannot bounce $WLAN_IF"
  fi
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
  # should give restarted services a moment to settle before the caller re-checks
  local failed=" $1 "
  [[ "$failed" == *" powersave "* ]] && heal_powersave
  [[ "$failed" == *" ts-backend "* || "$failed" == *" ts-peer "* ]] && heal_tailscale
  [[ "$failed" == *" wlan "* ]] && heal_wlan
  if [[ "$NEEDS_SETTLE" == "1" && -z "$DRYRUN" ]]; then
    log "settling ${SETTLE_SECS}s after restart/bounce..."
    sleep "$SETTLE_SECS"
  fi
  return 0
}

main() {
  resolve_wlan_if
  log "=== run start (if=$WLAN_IF${DRYRUN:+, dryrun}${DEMO:+, demo=$DEMO}) ==="
  if [[ "$(id -u)" -ne 0 ]]; then
    warn "not running as root — checks run, but heals may fail"
  fi

  local failed
  failed=$(run_checks)
  if [[ -z "$failed" ]]; then
    log "healthy: all checks passed"
    return 0
  fi

  log "UNHEALTHY: [$failed] — starting self-heal"
  self_heal "$failed"

  failed=$(run_checks)
  if [[ -z "$failed" ]]; then
    log "recovered: healthy after self-heal"
    return 0
  fi
  log "STILL UNHEALTHY after self-heal: [$failed]"
  return 1
}

main "$@"
