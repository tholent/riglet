# Riglet

A self-hosted web application for browser-based control of amateur radios over a local LAN. Riglet runs on a Raspberry Pi 4 co-located with your radios, providing remote frequency/mode/PTT control, audio streaming, and live waterfall display from any device on the network.

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

  ui/                  # Frontend (SvelteKit SPA)
    src/               # Svelte components and routes
    build/             # Production build output

  image/               # Raspberry Pi image build
    config.ini         # rpi-image-gen profile
    packages.txt       # apt packages to install
    scripts/           # Post-install hooks
    files/             # systemd units, default config
```

## Backend Development

### Setup

```bash
cd server
uv sync
```

### Run Development Server

```bash
cd server
uv run uvicorn server.main:app --reload
```

The backend runs on `http://localhost:8080` in simulation mode (no hardware required).

### Testing, Linting, and Type Checking

```bash
cd server
uv run pytest                    # run full test suite
uv run pytest tests/test_foo.py::test_name  # run a single test
uv run ruff check .              # lint
uv run ruff check --fix .        # lint + auto-fix
uv run mypy .                    # type check (strict mode)
```

## Frontend Development

### Setup

```bash
cd ui
npm install
```

### Run Development Server

```bash
cd ui
npm run dev
```

The dev server runs on `http://localhost:5173` and proxies `/api` requests to the backend at `localhost:8080`.

### Production Build

```bash
cd ui
npm run build
```

Output goes to `ui/build/`.

## Running Locally

1. Start the backend (from `server/`):
   ```bash
   uv run uvicorn server.main:app --reload
   ```

2. In a new terminal, start the frontend dev server (from `ui/`):
   ```bash
   npm run dev
   ```

3. Open `http://localhost:5173` in your browser.

The backend runs in simulation mode — no hardware is required. The setup wizard will be disabled if you manually add a radio to the config first.

## Image Build

The `image/` directory contains an `rpi-image-gen` profile for building a flashable Raspberry Pi OS image for Pi 4 Bookworm 64-bit. This includes all services, dependencies, and the post-install script that configures the system on first boot.

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
