# Swipe Dating — Python R&D

A Python recreation of the Swipe Dating synthetic research app. It preserves the behavior of the JavaScript baseline at commit `5c6b35e8b133f4b34224785eb4fc1e7ab61423a4` while keeping the production safety gates closed.

This repository includes:

- framework-independent adult, discovery, matching, conversation, relationship-phase, proximity, location-grant, risk, marketplace, and storage rules;
- a synthetic in-memory FastAPI adapter;
- a deterministic scenario simulator;
- a Tkinter desktop app for laptop research;
- executable privacy and governance checks.

It does **not** provide real authentication, age assurance, users, Bluetooth scanning, location collection, network messaging, E2EE, billing, moderation operations, or production deployment.

## Quick start

Python 3.12 or 3.13 is required. With [uv](https://docs.astral.sh/uv/):

```bash
uv sync --all-extras
uv run swipe-simulate
uv run swipe-desktop
```

The desktop command uses Python's standard Tkinter module. On a minimal or headless Python installation, install the matching OS `python-tk` package or use a Python distribution that includes Tk. Domain, API, simulation, and tests do not require a display server.

Run the local synthetic API:

```bash
uv run swipe-api
```

Then visit `http://127.0.0.1:8080/docs` or `http://127.0.0.1:8080/healthz`.

## Verify

```bash
uv run pytest --cov=swipe_dating --cov-branch
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run swipe-governance
```

See [docs/BASELINE.md](docs/BASELINE.md), [docs/PARITY_MATRIX.md](docs/PARITY_MATRIX.md), and [docs/PRODUCTION_GAPS.md](docs/PRODUCTION_GAPS.md) for scope and limitations.

## Release state

```text
PYTHON_RND_SYNTHETIC_ONLY
REAL_USER_CLOSED_BETA_BLOCKED
PRODUCTION_BLOCKED_HUMAN_APPROVALS_REQUIRED
```
