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
