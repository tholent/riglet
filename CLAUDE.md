# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (`server/`)

All backend commands run from `server/` using `uv`:

```bash
uv sync                        # install/update all deps (runtime + dev)
uv run pytest                  # run full test suite
uv run pytest tests/test_foo.py::test_name  # run a single test
uv run ruff check .            # lint
uv run ruff check --fix .      # lint + auto-fix
uv run mypy .                  # type check (strict mode)
uv run uvicorn server.main:app --reload  # run dev server on port 8080
```

Ruff, mypy, and pytest must all pass clean before committing.

### Frontend (`ui/`)

```bash
npm install          # install deps (first time)
npm run dev          # dev server at :5173, proxies /api → localhost:8080
npm run build        # production build → ui/build/
```

## Architecture

See `.state/OVERVIEW.md` for full system design. The implementation plan with task status is in `.state/PLAN.md`.

### What Riglet does

Browser-based ham radio control over LAN. Runs on a Raspberry Pi 4 co-located with the radios. Provides CAT control (frequency, mode, PTT), audio streaming (RX and TX), and live waterfall display — all via WebSocket from a Svelte SPA served by FastAPI.

### Backend structure (`server/`)

- **`config.py`** — Pydantic v2 models for the config schema. `RigletConfig` is the root; it validates cross-radio uniqueness (serial ports, audio devices, rigctld ports, radio IDs). `load_config` / `save_config` handle YAML I/O atomically. `default_config()` returns an empty config that triggers the setup wizard.
- **`state.py`** — `RadioInstance` (per-radio state + rigctld TCP connection + asyncio polling loop) and `RadioManager` (dict of instances, lifecycle). `RadioInstance` contains: rigctld StreamReader/Writer; state fields (freq, mode, ptt, online, rx_volume, tx_gain, nr_level); asyncio polling task; WebSocket refs (control/audio/waterfall). `RigctldError` exception raised on Hamlib error codes. Simulation mode: if rigctld is unreachable at startup, `RadioInstance.connect_rigctld()` sets `simulation=True` and subsequent reads return mocked data — enables UI development without hardware. Polling loop (configurable interval, default 100ms) calls `poll_once()` which queries freq/mode/smeter, compares to current state, and sends changed fields to `ws_control`.
- **`deps.py`** — Shared FastAPI dependency functions (`get_manager`, `get_radio`, `RadioDep`) extracted to break circular imports between `main.py` and routers.
- **`main.py`** — FastAPI app with lifespan context manager. Startup: loads config (defaults to `default_config()` if file missing), creates `RadioManager`, starts it (connects radios, begins polling). Shutdown: stops manager and closes all radios. Dependency functions: `get_manager()` returns the app-state manager; `get_radio(radio_id)` resolves a radio by ID (404 on not found). RFC 7807 exception handler for Pydantic `ValidationError` returns 409 Conflict. Mounts static files (if `/opt/riglet/app/static` exists) and routers at `/api` prefix. Uvicorn entry point.
- **`routers/system.py`** — `/api/status`, `/api/config` (GET/POST), `/api/config/restart`. `write_env_files()` generates radio-specific environment files for rigctld units. `restart_services()` reloads systemd and restarts rigctld instances and the main service.
- **`routers/`** — One module per resource: `devices` (serial/audio enumeration, SSE hotplug), `cat` (freq/mode/PTT), `audio` (WebSocket PCM), `waterfall` (WebSocket FFT frames).
- **`devices.py`** — Serial and audio device discovery; SSE stream for udev hotplug events.

### Key design decisions

- **One rigctld daemon per radio** (systemd template unit `rigctld@.service`). The backend connects over TCP localhost. Polling interval defaults to 100ms, minimum 50ms, configurable per radio via `polling_interval_ms`.
- **Three WebSocket channels per radio**: control (bidirectional JSON), audio (bidirectional binary PCM s16le 16kHz), waterfall (server→client JSON FFT frames ~10fps).
- **Audio/FFT threading**: A dedicated asyncio daemon thread per radio owns its PipeWire capture stream, runs `numpy.fft`, and feeds an `asyncio.Queue`. The WebSocket handler drains the queue.
- **Simulation mode**: If rigctld is unreachable at startup, `RadioInstance` sets `simulation=True` and returns mocked values — allows UI development without hardware.
- **Config validation errors** use RFC 7807 Problem Details format with `409 Conflict`, listing each conflict by type, field path, conflicting radio ID, and value.

### Frontend structure (`ui/src/`)

- **`routes/+page.svelte`** — Main UI page. Redirects to `/setup` if `setup_required` flag is set in status. On load, mounts all three WebSocket channels (control, audio, waterfall).
- **`routes/setup/+page.svelte`** — Five-step wizard: hostname configuration, serial radio detection, audio device mapping, PTT method selection, review and apply.
- **`lib/api.ts`** — Typed REST client for all backend endpoints (config, status, device discovery, CAT commands, logs, Hamlib models).
- **`lib/websocket.ts`** — `ControlWebSocket` class for control channel with exponential backoff reconnect logic.
- **`lib/reconnect.ts`** — `waitForRestart()` utility that polls `/api/status` every 1 second with a 30-second timeout after a service restart.
- **`lib/audio/`** — `AudioManager.ts` (Web Audio API, getUserMedia stream capture and playback) and `pcm-worklet-processor.js` (s16le to Float32 bidirectional ring buffer in an AudioWorklet).
- **`lib/components/`** — UI components: `Waterfall` (scrolling canvas with HSL color map), `FrequencyDisplay`, `ModeSelector`, `PttButton`, `SmeterDisplay`, `AudioControls`.
- **`lib/components/wizard/`** — Setup wizard steps: `StepWelcome`, `StepDetectRadios`, `StepMapAudio`, `StepPttMethod`, `StepReviewApply`.

### Image build (`image/`)

rpi-image-gen profile for Raspberry Pi 4 Bookworm 64-bit. Contains `config.ini` (profile metadata), `packages.txt` (apt dependencies), and `scripts/01-configure.sh` (idempotent post-install: creates user, sets up Python venv, installs systemd units, hardens SSH).
