# Pi Setup

Steps that must be done manually on the Pi — these cannot be automated via CI.

## 1. Initial clone

```bash
git clone <repo-url> /opt/media-pi
```

## 2. Create the staging worktree

First ensure the `staging` branch exists on GitHub, then:

```bash
git -C /opt/media-pi worktree add /opt/media-pi-staging staging
```

You now have two independent working trees:
- `/opt/media-pi` → `main` (prod)
- `/opt/media-pi-staging` → `staging`

## 3. Install dev tooling

Run from `/opt/media-pi`:

```bash
bash scripts/install-dev-deps.sh
```

This installs `pre-commit` for your OS and registers the hooks in the repo.

## 4. Let the TUI control the daemon

The TUI's Daemon Start/Stop buttons run `sudo -n systemctl start|stop media-pi-daemon`.
Grant the **login user that runs the TUI** (check with `whoami`) passwordless `sudo` for
exactly those two commands. First confirm the `systemctl` path:

```bash
command -v systemctl   # usually /usr/bin/systemctl — update the rule below if it differs
```

Then create a narrow drop-in (replace `admin` with your TUI user):

```bash
sudo visudo -f /etc/sudoers.d/media-pi-daemon
```
```
admin ALL=(root) NOPASSWD: /usr/bin/systemctl start media-pi-daemon, /usr/bin/systemctl stop media-pi-daemon
```

Without this rule the buttons fail fast (no hang) and the TUI shows an error toast —
`sudo -n` never prompts for a password. The rule is intentionally limited to the two
exact commands.
