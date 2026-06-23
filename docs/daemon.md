# Daemon

There are a few shedule/heatbeat/notification based features/requirement in this architecture. 
 
The three known ones are:
- starting and stopping the camera for a saved event
- recieving and processing new events from the server
- automatic upload for new files in a target directory

Polling for all three of these would be far too much overhead, so instead we will have a daemon managed by `systemd`. 

All three of them with run as `asyncio` coroutines inside a single event loop. This structure enables us to add more triggers without spawning addoitional processes.
