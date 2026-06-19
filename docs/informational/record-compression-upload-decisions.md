[in draft - key points only]

# Recording pipeline decisions and technical information doc

`-input_format h264`: the camera has an encoder chip that compresses the video to H.264 before it is received by the raspbarry pi.
`VIDEO_CODEC=copy`: ffmpeg copies the data to the spoecified location without de and re coding it

This saves processing power on the raspberry pi

BASH codes:
```
# Exit codes:
#   0 success (file uploaded, confirmed, local deleted)
#   1 usage / config error
#   2 file missing / empty / still being written
#   3 upload failed (rclone exhausted retries)
#   4 register failed (API unreachable, auth rejected, bad ext, ...)
#   5 confirm failed (upload completed — row still has video_url=NULL on server;
#     the local file is retained so confirm can be re-run by hand)
```

rclone for upload
