# Pi Install Runbook

Target host:

- `pi@10.1.20.11`
- Repository checkout: `/home/pi/hermes-runtime`
- Hermes service: `hermes-serve.service`

## Update Runtime Repository

```bash
cd /home/pi/hermes-runtime
git pull --ff-only
mise run check
uv run --extra dev python -m pytest tests/test_end_to_end_flow.py
```

## Install Advisor Gate Plugin

Use the official Hermes plugin installer:

```bash
hermes plugins install poruru210/hermes-runtime/plugin/advisor-gate --force --enable
```

## Configure Commander Profile

Create or update the Commander profile with the official profile and config
commands. The Commander profile must have `kanban` in its profile config; using
`-t kanban` in a one-off chat is not enough for `kanban_create`.

```bash
hermes profile create commander --clone \
  --description "Plans user requests, creates Kanban task graphs, and does not perform implementation work directly."
hermes -p commander config set toolsets '[kanban, advisor_gate, skills]'
```

If the profile already exists, keep it and re-run only the config command:

```bash
hermes -p commander config set toolsets '[kanban, advisor_gate, skills]'
```

Register the runtime skills as an external skill directory:

```bash
hermes config set skills.external_dirs /home/pi/hermes-runtime/runtime-profile/skills
hermes config set skills.write_approval true
```

Then restart Hermes:

```bash
hermes gateway restart
```

If the official restart command hangs, use systemd on the Pi:

```bash
sudo systemctl restart hermes-serve.service
```

## Verify

```bash
systemctl is-active hermes-serve.service
hermes config check
hermes doctor
hermes plugins list --plain --no-bundled
hermes tools list
hermes -p commander profile show commander
```

Expected signs:

- `hermes-serve.service` is `active`.
- `advisor-gate` is enabled.
- `hermes doctor` reports `advisor_gate` under Tool Availability.
- `commander` profile exists.
- `commander` profile has `toolsets = [kanban, advisor_gate, skills]`.
- Repository checks pass.

Do not commit local logs, receipts, auth files, `.env`, or terminal captures
that contain secrets.
