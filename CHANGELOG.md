# CHANGELOG

<!-- version list -->

## v0.1.1 (2026-06-24)

### Bug Fixes

- Resolve REPO_ROOT two levels up in record/upload scripts; ignore runtime artifacts
  ([`08ae1c7`](https://github.com/foundersandcoders/media-pi/commit/08ae1c79ceea4c6155f42e5b7ed06f553dd8b938))


## v0.1.0 (2026-06-24)

### Bug Fixes

- Correct daemon systemd unit for the Pi
  ([`067aa9c`](https://github.com/foundersandcoders/media-pi/commit/067aa9cd09fe793ba6ff61b8646f01e5cd7fa9f5))

### Chores

- Modifies tui nav behaviour
  ([`e3ec892`](https://github.com/foundersandcoders/media-pi/commit/e3ec89296b63d014b5a3a87365d74f5139f05ac3))

- Restyles both selectable panels for consitent focus styling
  ([`3030157`](https://github.com/foundersandcoders/media-pi/commit/3030157669e2e7552f4cdcb0d56e28a0795a88f1))

### Code Style

- Implements tcss stylsheet for conistent styling
  ([`0c9ca1d`](https://github.com/foundersandcoders/media-pi/commit/0c9ca1d3923eb6ba9d66c7713c97055460828b52))

### Documentation

- Database.md initial schema and approach
  ([`fa02523`](https://github.com/foundersandcoders/media-pi/commit/fa0252397ff4a48ecbb844a3775e08275397f1d3))

- Explains daemon approach for incoming changes
  ([`43c4862`](https://github.com/foundersandcoders/media-pi/commit/43c48625a137cac98824a2c0f4a8cc12f6c18a90))

- Updates daemon.md with more accurate architecture
  ([`c8ecc11`](https://github.com/foundersandcoders/media-pi/commit/c8ecc1188498f332655d62f241a3c22d732d9d0f))

### Features

- Add upload pipeline daemon
  ([`efd6ab8`](https://github.com/foundersandcoders/media-pi/commit/efd6ab8fc65778eff0339ca4b923ee3997e26ec7))

- Allows you to navigate the failed uploads panel and retry upload
  ([`4d1dfae`](https://github.com/foundersandcoders/media-pi/commit/4d1dfae422d927d1fceede431257ec51cab09945))

- Create a video row when recording starts
  ([`294065c`](https://github.com/foundersandcoders/media-pi/commit/294065c0cd811303d6a9bda26a08e97ef8059701))

- Daemon startup recovery and liveness, shown in the TUI
  ([`a0ad605`](https://github.com/foundersandcoders/media-pi/commit/a0ad6055755364f7f57111223689c62b7c4ef804))

- Implements core filming and upload scripts
  ([`2e7108a`](https://github.com/foundersandcoders/media-pi/commit/2e7108a8ea19544421512acbb4c4eeccc9436b15))

- Inits tui with basic files structure
  ([`ba9bdbe`](https://github.com/foundersandcoders/media-pi/commit/ba9bdbe92fe0ce7cdcc1516b4965d562f02d55b2))

- Normalise video status into a status_mapping
  ([`3520d5a`](https://github.com/foundersandcoders/media-pi/commit/3520d5aeecc0ba69ab4f892814cc3faa7d993532))

- Retrieves video data and displays as read only widgets (video tracking and failes uplaods)
  ([`827c915`](https://github.com/foundersandcoders/media-pi/commit/827c91542933748c2a70a5a6af00ea5e322f9e40))

- **db**: Implements data base schema with seed data
  ([`c48db4b`](https://github.com/foundersandcoders/media-pi/commit/c48db4b239cba57dc4b732937a43595e166faab1))

### Refactoring

- Moves core scripts folder to src
  ([`ee55e11`](https://github.com/foundersandcoders/media-pi/commit/ee55e11026f1ea34bcd32bf2b56b5d3585ab286c))

- Refactors tui directory. /tui now contains /widgets
  ([`559ce25`](https://github.com/foundersandcoders/media-pi/commit/559ce25880e320c452703fd35aa9bac9abb4e600))


## v0.0.0 (2026-06-17)

- Initial Release
