# Riglet

A self-hosted web application for browser-based control of amateur radios over a local LAN. Riglet runs on a Raspberry Pi 4 co-located with your radios, providing remote frequency/mode/PTT control, audio streaming, and live waterfall display from any device on the network.

## Prerequisites

- **Target**: Raspberry Pi 4 (64-bit) with Raspberry Pi OS Lite (Bookworm)
- **Development**: macOS, Linux (any with Python 3.11+)
- **Python**: 3.11 or later

## Getting Started

### Install Dependencies

Riglet uses `uv` for dependency management. Install the project and all development tools:

```bash
cd server
uv sync
```

This creates a virtual environment and installs all runtime and development dependencies.

### Run Tests

```bash
cd server
uv run pytest
```

All tests must pass before code is merged.

### Lint and Type Check

Riglet uses Ruff for linting and mypy for strict type checking.

```bash
cd server
uv run ruff check .
uv run mypy .
```

Both must pass without errors.

## Project Structure

```
riglet/
  server/              # Python backend (FastAPI)
    config.py          # Configuration models and I/O
    state.py           # Radio instance and manager classes
    main.py            # FastAPI application and lifespan
    devices.py         # Serial and audio device discovery
    routers/           # API endpoint modules
    tests/             # Unit tests
    pyproject.toml     # Dependencies and tool configuration

  image/               # Raspberry Pi image build
    config.ini         # rpi-image-gen profile
    packages.txt       # apt packages to install
    scripts/           # Post-install hooks
    files/             # systemd units, default config

  ui/                  # Frontend (Svelte SPA, built separately)
```

## Architecture

For a complete overview of the system architecture, API contracts, configuration schema, and deployment model, see [`.state/OVERVIEW.md`](.state/OVERVIEW.md).

Key highlights:

- **Backend**: FastAPI + uvicorn on port 8080
- **Radio control**: Hamlib rigctld (one daemon per radio)
- **Audio**: PipeWire with real-time PCM streaming over WebSocket
- **Config**: Single YAML file at `/etc/riglet/config.yaml` with atomic write semantics
- **Config validation**: Pydantic models with cross-radio uniqueness constraints

## Contributing

- Always run tests, linting, and type checking before submitting code
- Update `.state/PLAN.md` and `.state/ARCHIVE.md` when tasks are complete
- Keep the documentation in sync with code changes