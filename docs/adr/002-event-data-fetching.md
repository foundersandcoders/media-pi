# DR-002: Pull lesson events by polling a REST endpoint

**Status:** Accepted
**Date:** 30/06/2026

## Context

The Pi needs the lesson schedule (held on the FAC server) to film automatically. Schedule
data is low-velocity and the Pi only reaches the server outbound — so pull beats push.

## Decision

**Poll a dedicated REST `GET` every 5 min and sync the result into the local `event` table.**

- **Transport** — REST `GET` (idempotent, curl-testable over SSH), not GraphQL.
- **Auth** — separate read-only key, scope `media-pi:schedule`; the key identifies the Pi
  server-side (no `pi_id` in URL). New `FAC_SCHEDULE_URL` env var.
- **Window** — today 09:00–21:00 London. Forward edge = upcoming lessons; 9am back-edge lets a
  rebooted Pi resume one already running. Converted to the server's UTC.
- **Merge** — response is `{ remote_id, workshop_name, start_time, end_time }`. Upsert on
  `remote_id`; `workshop_name` get-or-created into `workshop_mapping`; cohort stays a hardcoded
  placeholder. Hard-delete any future, in-window local event absent from the response (cancelled).
- **Scheduler** — a coroutine, woken by an `asyncio.Event` after each merge, (re)plans from the
  table. An in-progress recording is immutable: runs to the `end_time` snapshotted at start;
  mid-recording cancellations/time-changes ignored, first recording wins overlaps, reboot resumes
  into a live window. A manual stop of a *scheduled* recording must confirm; ad-hoc stops freely.

## Considered

- **Webhook / MQTT / SSE push** — all need inbound infra or a babysat connection for latency
  we don't need on low-velocity data.
- **Reuse the `watch:upload` key** — single-scope exact match would conflate read + write and
  block independent revocation.
- **Soft-delete cancelled events** — buys nothing; workshop/cohort are already mapped, so a
  deleted row only loses start/end, which the server re-supplies next poll.

## Consequences

- Add a `remote_id` column to the local `event` table (the dedup key).
- Server work (fac-cra): new REST route, a `media-pi:schedule` key, and `core.api_keys` mapping
  a key → the Pi's cohort/room.
- Config: new `FAC_SCHEDULE_URL` + `POLL_INTERVAL` in `.env`.
- Recorder state file gains a scheduled-vs-ad-hoc flag + snapshot `end_time` for the stop guard.
- Up to ~5 min staleness; a lesson created <5 min before start can be missed — acceptable.
- A push-to-wake can be layered over the poll later if latency ever matters.
- Deferred: other manual-conflict cases; cohort seeding; the scheduler implementation (step 4).
