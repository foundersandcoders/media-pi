from pathlib import Path

_CORE = Path(__file__).parent.parent / "core"
RECORD = str(_CORE / "record.sh")
UPLOAD = str(_CORE / "upload.sh")
# &&&& new (scaffold)
FETCH = str(_CORE / "fetch_events.sh")  # pulls the lesson schedule
DAEMON_SERVICE = "media-pi-daemon"
