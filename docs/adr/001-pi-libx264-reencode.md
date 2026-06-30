# DR-001: Re-encode live on the Pi with libx264 (revert `VIDEO_CODEC=copy`)

**Status:** Accepted
**Date:** 30/06/2026
*Supersedes the `VIDEO_CODEC=copy` decision in [`000`](./000-initial%20decisions.md).*

## Context

`copy` was adopted to fix laggy audio blamed on `libx264` falling behind. Wrong diagnosis:
the Pi had reshuffled ALSA and bound the **Instalink Pro** mic (which lags) over the **DJI
Mic Mini**. x264 was fine all along. So the reason to stream-copy is gone — and `copy` costs
~870 MB / 10-min segment (CBR), too big for reliable uploads/storage.

## Decision

Re-encode live with **`-c:v libx264 -preset veryfast -crf 23`**, audio **`-b:a 128k`**; stop
setting `VIDEO_CODEC=copy`. H.264/x264 fits the bar — modern, ubiquitous, CRF compresses
well without going too lossy.

## Considered

Bar: well-supported, modern, compresses well but not too lossy.

- **HEVC/x265** — better compression, but heavier encode + licensing/playback baggage.
- **VP9** — slow encode, less ubiquitous; no advantage here.
- **AV1** — best compression, but encoders too heavy for realtime on the Pi.
- **FFV1** — lossless; files balloon — opposite of the goal.

## Consequences

- CRF (Constant Rate FActor) is VBR (variable Bitrate), so segment sizes now vary with scen
- Need to update muxer to split by frame
- A too-slow encoder now shows as dropped frames, not audio starvation.
- Follow-ups (flagged): mic-binding tests; realtime camera-processing health check.
