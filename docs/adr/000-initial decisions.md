> Note: This is a record of backlogged decisions created though personal notes kept whilst developing - verified with commit logs

---

# Segmented recording

## Decision
ffmpeg records via its **segment muxer**, rotating to a new `session_<ts>_NNN.mp4`. Each finished segment uploads while the next records.

## Why
A single continuous file meant nothing uploaded until the session stopped which resulted in large uploads that often hit our upload time limit. 

## Consequences
The daemon watcher now owns per-segment DB rows by creating a `recording` row for the active/newest segment, flips finished ones to `in_queue`

---

# Remote access via Tailscale

## Decision
The Pi is reached over a Tailscale tailnet (`ssh admin@media-pi`)

## Why
For team access from outside the classroom LAN.

---

# Single asyncio daemon under systemd

## Decision
Scheduling, upload-queue management, and (planned) server-event handling run as
`asyncio` coroutines in one event loop, owned by `systemd`

## Why
Polling adds latency between trigger and effect and load on the Pi; one event loop lets new triggers be added without extra processes.

---

# Python is the sole DB writer

## Decision
The shell scripts shell out to Python for any DB write; bash carries failures out via
exit codes only.

## Why
One writer avoids cross-process SQLite races and keeps a single place that understands the schema. 

---

# Notification-based TUI refresh via a sentinel file

## Decision
DB writers `touch` `data/.ui-dirty`; the TUI watches that sentinel with `watchfiles`
and reloads.

## Why
SQLite has no cross-process change notification, and the TUI + daemon are separate processes. The writer nudges the reader. Watching the sentinel (not `data/`) avoids refresh storms from `-wal` churn during uploads.

---

# `VIDEO_CODEC=copy` on the Pi

## Decision
The Pi stream-copies the camera's onboard H.264 (`-input_format h264` + `-c:v copy`);
the Mac dev path keeps `libx264`.

## Why
The Pi 5 at 1080p30 ran sub-realtime (~0.93×), and a live source that falls behind starves the audio input.

## Consequences
The camera emits a near-constant ~12 Mbps CBR, so files are large (~870 MB per 10-min segment) regardless of scene compared to the previous compression method (`libx264 -crf 23` encoding, not from copy.)

---
