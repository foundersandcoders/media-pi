# Daemon

## Overview
There are a few shedule/heatbeat/notification based features/requirement in this architecture. 
 
The three known ones are:
- starting and stopping the camera for a saved event
- recieving and processing new events from the server
- Managing video uplaod queue

Polling for all three of these would introduce latency between trigger and effect, so instead we will have a daemon managed by `systemd`. It will also be a much cleaner architecture to implement, and reduce load on the raspberry pi.

All three of them with run as `asyncio` coroutines inside a single event loop. This structure enables us to add more triggers without spawning addoitional processes.

## Architecture

### Scheduler

```mermaid
flowchart TD
    A[daemon starts] --> B[query next event from DB]
    B --> C{event found?}
    C -->|no| D[asyncio.sleep 3600s\ncheck again in 1hr]
    C -->|yes| E[calculate delay\nstart_time minus now]
    E --> F[asyncio.sleep delay]
    D -->|CancelledError| B
    F -->|CancelledError| B
    F -->|timer fires| G[record.sh start]
    G --> H[mark event started in DB]
    H --> B

    I([new event arrives\nvia MQTT or TUI]) --> J[scheduler.reschedule\ntask.cancel]
    J -.->|CancelledError raised\nin current sleep| B
```

### Upload Pipeline

The pipeline is **UPDATE-only**: a `video` row is created at RECORD time (with its
cohort/workshop), and the daemon only transitions that row's status as the file moves
through the upload. Statuses live in the `status_mapping` table
(`recording → in_queue → uploading → uploaded / failed`).

```mermaid
flowchart TD
    A[daemon starts] --> B[startup recovery\nreset uploading to in_queue\nenqueue all in_queue rows]
    B --> Q([asyncio.Queue warm])

    W[watchfiles awatch\nrecordings dir] -->|finished .mp4\nnot the active recording| M[find video row\nby file_path]
    M -->|row exists and\nrecording or in_queue| U1[UPDATE status=in_queue]
    M -->|no row / already past| X[skip]
    U1 --> P[queue.put video_id, path]
    P --> Q

    Q --> G[queue.get\nawaits next item]
    G --> U[UPDATE status=uploading]
    U --> S[upload.sh path]
    S -->|exit 0| K[UPDATE status=uploaded]
    S -->|exit non-zero| F[UPDATE status=failed\nset error_mapping_id]
    K --> G
    F --> G
```

### MQTT Listener

```mermaid
flowchart TD
    A[daemon starts] --> B[connect to broker\nhost from .env]
    B --> C[subscribe\nupload/confirmed/+\nevents/new]
    C --> D[paho loop_start\nruns in own thread]
    D --> E{on_message}
    E -->|upload/confirmed| F[UPDATE video\nstatus=uploaded]
    E -->|events/new| G[INSERT event row\nto DB]
    G --> H[scheduler.reschedule]
    F --> E
    H --> E
    B -->|connection lost| R[paho auto-reconnect\nexponential backoff]
    R --> B
```
