# Riglet

[![Pytest](https://github.com/tholent/riglet/actions/workflows/pytest.yml/badge.svg)](https://github.com/tholent/riglet/actions/workflows/pytest.yml)
[![Mypy](https://github.com/tholent/riglet/actions/workflows/mypy.yml/badge.svg)](https://github.com/tholent/riglet/actions/workflows/mypy.yml)
[![Ruff](https://github.com/tholent/riglet/actions/workflows/ruff.yml/badge.svg)](https://github.com/tholent/riglet/actions/workflows/ruff.yml)
[![JS Lint](https://github.com/tholent/riglet/actions/workflows/js-lint.yml/badge.svg)](https://github.com/tholent/riglet/actions/workflows/js-lint.yml)
[![JS Test](https://github.com/tholent/riglet/actions/workflows/js-test.yml/badge.svg)](https://github.com/tholent/riglet/actions/workflows/js-test.yml)

A self-hosted web application for browser-based control of amateur radios over a local LAN. Riglet runs on a Raspberry Pi 4 co-located with your radios, providing remote frequency/mode/PTT control, audio streaming, live signal visualization, and client-side DSP — all from any browser on the network.

## Features

- **CAT control** — frequency, mode, PTT, VFO, squelch, RF gain, CTCSS via Hamlib rigctld
- **Audio streaming** — full-duplex PCM over WebSocket; RX playback and TX capture in the browser
- **Client-side DSP** — bandpass filter, notch filter, noise reduction (Wiener), 3-band EQ, compressor
- **Signal visualization** — six pluggable modes: waterfall, spectrogram (3D), oscilloscope, spectrum, constellation, phase
- **Frequency presets** — save, recall, import/export; grouped by band
- **S-meter display** — real-time signal strength from the polling loop
- **Password-protected access** — session-cookie auth (bcrypt + itsdangerous); login page, 30-day session, logout; first-run password setup in wizard
- **Setup wizard** — guided first-run configuration for radio detection, audio mapping, PTT method, and password setup
- **Simulation mode** — full UI works without hardware; simulated radios return mocked data

## Project Structure

```
riglet/
  server/              # Python backend (FastAPI)
    config.py          # Configuration models and I/O (Pydantic v2)
    state.py           # RadioInstance, RadioManager, polling loop
    main.py            # FastAPI app, lifespan, routing
    auth.py            # SessionAuthMiddleware, bcrypt hashing, session token I/O
    devices.py         # Serial and audio device discovery
    bandplan.py        # Amateur band definitions
    modes.py           # Radio mode constants
    deps.py            # Shared FastAPI dependency functions
    routers/           # API endpoint modules (auth, cat, audio, waterfall, devices, system)
    tests/             # pytest test suite
    pyproject.toml     # Dependencies and tool configuration (uv)

  ui/                  # Frontend (SvelteKit SPA, Svelte 5)
    src/
      routes/          # +page.svelte (main UI), setup/ (wizard), login/ (auth gate)
      lib/
        components/    # UI components (FrequencyDisplay, Knob, TuningKnob, VisualizationPanel, …)
        audio/         # AudioManager, DspChain, audio worklet processors
        viz/           # Pluggable renderer system (waterfall, oscilloscope, constellation, …)
        layout/        # Panel layout engine and defaults
    static/            # Publicly served assets (audio worklets, favicon)
    build/             # Production build output (generated)

  deployment/          # Raspberry Pi deployment artifacts
    config.ini         # rpi-image-gen profile (Pi 4, Bookworm, arm64)
    packages.txt       # apt packages
    scripts/           # Post-install configuration hooks
    files/             # systemd units (riglet.service, rigctld@.service), default config
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
uv run uvicorn main:app --reload --port 8080
```

The backend starts in simulation mode if no config file is found — no hardware required. The config is read from `~/.config/riglet/config.yaml` by default, or from the path in the `RIGLET_CONFIG` environment variable.

### Testing, Linting, and Type Checking

```bash
cd server
uv run pytest                                    # run full test suite
uv run pytest tests/test_foo.py::test_name      # run a single test
uv run ruff check .                              # lint
uv run ruff check --fix .                        # lint + auto-fix
uv run mypy .                                    # type check (strict mode)
```

All three must pass clean before committing.

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

### Type Checking and Tests

```bash
cd ui
npm run check     # svelte-check (TypeScript + Svelte type checking)
npm test          # vitest (unit tests)
```

### Production Build

```bash
cd ui
npm run build
```

Output goes to `ui/build/`.

## Running Locally (No Hardware)

1. Start the backend (from `server/`):
   ```bash
   uv run uvicorn main:app --reload --port 8080
   ```

2. In a new terminal, start the frontend (from `ui/`):
   ```bash
   npm run dev
   ```

3. Open `http://localhost:5173` in your browser.

On first run, the setup wizard will appear. Add a simulated radio to get started without any hardware. The simulated radio returns mocked frequency, mode, and S-meter data and fully exercises the UI.

## Deployment (Raspberry Pi)

The `deployment/` directory contains a [rpi-image-gen](https://github.com/raspberrypi/rpi-image-gen) profile for building a flashable Pi OS image (Pi 4, Bookworm 64-bit). The image includes all runtime dependencies, systemd units for riglet and rigctld, and an idempotent post-install script.

The backend is managed by `riglet.service`; one `rigctld@<radio-id>.service` instance runs per configured radio. The frontend is served as static files from the FastAPI process.

## Architecture

For the full system design, API contracts, and configuration schema see [`.state/OVERVIEW.md`](.state/OVERVIEW.md).

### Key design decisions

- **One rigctld daemon per radio** — Hamlib runs as a systemd template unit. The backend connects over TCP localhost and polls at a configurable interval (default 100 ms, minimum 50 ms).
- **Three WebSocket channels per radio** — control (bidirectional JSON), audio (bidirectional binary PCM s16le 16 kHz mono), waterfall (server→client JSON FFT frames ~10 fps).
- **Client-side DSP chain** — Web Audio API graph: bandpass → notch → noise reduction (AudioWorklet, Wiener filter) → compressor → EQ → squelch → gain.
- **Pluggable visualization renderers** — all renderers implement a common `Renderer` interface; switching modes swaps the renderer without touching the data pipeline.
- **Simulation mode** — if rigctld is unreachable at startup, `RadioInstance` sets `simulation=True` and returns mocked data. Disabled radios also start as simulation instances.
- **Config path** — `~/.config/riglet/config.yaml` on dev; overridable via `RIGLET_CONFIG` environment variable (set by systemd on Pi). Atomic writes via a temp-file rename.
- **Reactive UI state** — Svelte 5 runes (`$state`, `$derived`, `$effect`). Class instance mutations use explicit state promotion to trigger re-renders.

## Contributing

- Run `uv run pytest`, `uv run ruff check .`, and `uv run mypy .` before committing backend changes.
- Run `npm run check` before committing frontend changes.
- Keep `.state/OVERVIEW.md` and `.state/PLAN.md` in sync with significant architectural decisions and task status.
