# Riglet -- System Overview

## What It Is

Riglet is a self-hosted web application that gives a ham radio operator browser-based control of one or more radios over a local LAN. The system runs on a Raspberry Pi 4 (64-bit) co-located with the radios. No internet access is required or assumed.

The target operator may have any number of radios (e.g., Icom IC-7300, Yaesu FT-991A, Kenwood TS-590), each with its own USB audio interface, and operates in SSB voice and FT8 digital modes. Each radio operates independently via its own browser tab.

## Problem Statement

Controlling amateur radios typically requires physical proximity to the equipment. Riglet decouples the operator from the radio room by exposing CAT control, audio streaming, and a live waterfall display through a browser UI accessible from anywhere on the LAN -- enabling remote operation from a laptop or desktop without proprietary software or internet dependency.

## Current State

The project is at **initial commit**. No source code exists yet. The handoff document (`riglet-handoff.md`) defines the full architecture, API contracts, config schema, deployment model, and v1 definition of done. Implementation has not started.

---

## Architecture

### High-Level Topology

```
Browser (laptop/desktop on LAN)
  |-- SPA served as static files from FastAPI
  |-- REST API calls --> FastAPI backend
  |-- WebSocket connections (per radio):
        |-- Control WS:    bidirectional JSON (freq, mode, PTT, S-meter)
        |-- Audio WS:      bidirectional binary PCM (s16le, mono, 16kHz)
        |-- Waterfall WS:  server-->client JSON FFT frames (~10 fps)

Raspberry Pi 4 (co-located with radios)
  |-- FastAPI backend (Python, uvicorn, port 8080)
  |-- rigctld x N (one Hamlib daemon per radio, ports 4532+)
  |-- PipeWire / pipewire-pulse (audio routing)
  |-- ser2net (raw serial forwarding for DigiLink)
  |-- WSJT-X (optional, independent, talks directly to rigctld)
```

### Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| All radios always connected | rigctld runs as N permanent daemons. Tabs are independent viewports, not a shared resource. No teardown on tab switch. |
| No PTT interlock across radios | Simultaneous TX is the operator's responsibility. Antenna/RF planning is out of scope for software. |
| Single operator model | One WebSocket client per radio at a time. No multi-user concurrency. |
| REST for commands, WebSocket for streams | Freq/mode/PTT changes are REST POSTs. Audio, FFT, and state-push events use WebSocket. PTT via WebSocket is preferred for latency. |
| Simulation mode | If rigctld is unreachable at startup, backend returns mocked values. Enables UI development without hardware. |
| Config-driven startup | Single YAML config at `/etc/riglet/config.yaml`. Changes require an explicit restart endpoint. |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, uvicorn |
| Dependency management | uv (replaces pip/venv directly) |
| Config validation | Pydantic (zero-cost — already a FastAPI dep) |
| Linting | Ruff |
| Type checking | mypy |
| Radio control | Hamlib (rigctld), one daemon per radio |
| Audio subsystem | PipeWire / pipewire-pulse, ALSA |
| Frontend | Single-page application (static files served by FastAPI) |
| Browser audio | Web Audio API AudioWorklet (PCM ring buffer); Opus fallback if latency exceeds 150ms |
| Serial/device | ser2net (DigiLink), pyserial (implicit), udev for hotplug |
| Service management | systemd (template units for rigctld, dedicated unit for FastAPI) |
| Discovery | Avahi / mDNS (riglet.local) |
| OS | Raspberry Pi OS Lite 64-bit (Bookworm) |
| Image build | rpi-image-gen |

---

## Data Flows

### 1. Radio Control (CAT)

```
Browser --> REST POST /api/radio/{id}/cat/freq --> FastAPI --> rigctld (TCP port) --> radio
Radio state change --> rigctld --> FastAPI polling --> Control WebSocket --> Browser
```

Both REST and WebSocket can be used for commands (freq, mode, PTT, nudge). WebSocket is preferred for PTT to minimize latency. The backend polls rigctld and pushes state changes (freq, mode, PTT, S-meter) to the Control WebSocket.

### 2. Audio (RX and TX)

```
RX: Radio --> USB audio interface --> PipeWire --> FastAPI --> Audio WebSocket (binary PCM) --> Browser AudioWorklet --> speakers
TX: Browser mic --> AudioWorklet --> Audio WebSocket (binary PCM) --> FastAPI --> PipeWire --> USB audio interface --> radio (only when PTT active)
```

Format: raw PCM, s16le, mono, 16 kHz, 20ms chunks (640 bytes each). TX audio sent while PTT is inactive is silently dropped.

### 3. Waterfall

```
PipeWire audio capture --> FFT (server-side, 256 bins) --> Waterfall WebSocket (JSON, ~10 fps) --> Browser canvas
```

Values are 0.0 to 1.0, log-normalized. Span is determined by PipeWire capture sample rate (48 kHz).

### 4. Device Discovery and Hotplug

```
USB event --> udev --> Backend detection --> SSE stream (/api/devices/events)
                                         --> REST endpoints (/api/devices/serial, /api/devices/audio)
```

Frontend subscribes to SSE for live hotplug events. Disconnected devices are flagged but not auto-cleared from config.

### 5. Config Change and Service Restart

```
UI --> POST /api/config (validate + write) --> POST /api/config/restart
  1. Check no radio has PTT active (409 if any does)
  2. Push service_restart event to all WebSocket clients
  3. Write new .env files from config
  4. systemctl restart rigctld@* and riglet
  5. Client enters reconnect loop (polls /api/status every 1s, 30s timeout)
```

---

## Config Schema

Single source of truth: `/etc/riglet/config.yaml`

Top-level sections: `operator` (callsign, grid), `network` (hostname, port), `audio` (sample rate, chunk size), `radios` (array of radio definitions).

Each radio entry contains: id, name, hamlib_model, serial_port, baud_rate, ptt_method, audio_source, audio_sink, rigctld_port, enabled.

Validation rules:
- Serial ports must be unique across radios
- Audio source/sink pairs must be unique across radios
- Disabled radios may have empty audio fields
- Config is read at startup only; runtime changes require explicit restart

---

## File Structure (Target)

```
riglet/
  image/                          # Raspberry Pi image build
    config.ini                    # rpi-image-gen profile
    packages.txt                  # apt package list
    scripts/01-configure.sh       # post-install script
    files/
      riglet.service              # FastAPI systemd unit
      rigctld@.service            # Hamlib daemon template unit
      config.yaml.default         # default config (triggers setup wizard)

  server/                         # Backend application
    main.py                       # FastAPI app, startup/shutdown
    state.py                      # RadioManager, RadioInstance
    config.py                     # config.yaml read/write/validate
    devices.py                    # serial + audio device discovery, SSE hotplug
    pyproject.toml                # dependencies, ruff + mypy config
    routers/
      system.py                   # /api/status, /api/config, /api/logs
      devices.py                  # /api/devices/*
      cat.py                      # /api/radio/{id}/cat/*
      audio.py                    # /api/radio/{id}/audio/* + audio WS
      waterfall.py                # /api/radio/{id}/ws/waterfall
```

The SPA frontend is served as static files from `/opt/riglet/app/static/` via FastAPI's StaticFiles mount. The frontend framework is not specified in the handoff.

---

## Deployment Model

- **Image-based**: A custom Raspberry Pi OS image is built with rpi-image-gen, flashed to SD card
- **First boot**: If no radios are enabled in config, the backend serves a setup wizard at port 8080
- **mDNS**: avahi-daemon advertises `riglet.local` immediately on boot
- **User**: All services run as the `ham` user (groups: dialout, audio, plugdev)
- **Python**: Dependencies managed with uv; virtual environment at `/opt/riglet/venv`
- **App location**: `/opt/riglet/app/`

---

## v1 Definition of Done

A successful v1 means:

1. Fresh SD card image boots a Pi 4 and `riglet.local:8080` is reachable within 60 seconds
2. One radio (IC-7300) connected via USB; setup wizard detects it, assigns audio, passes CAT test
3. Main UI shows: live waterfall (~10 fps), correct frequency, working frequency/mode controls, RX audio in browser, PTT + TX audio from browser mic
4. Config changes persist across Pi reboot

### Explicitly Out of Scope for v1

- Multi-radio tabs (second and third radio)
- WSJT-X frequency sync to UI
- Multi-user / shared operation
- Internet remote access (outside LAN)
- Mobile app
- Logging / QSO database integration

---

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| PipeWire device names change between reboots | Medium | Match devices by USB VID/PID, not full device string. Store VID/PID in config alongside device name. |
| Audio latency unacceptable over LAN | Low | Prototype audio pipeline first. Fallback to Opus encoding if raw PCM exceeds 150ms. |
| rigctld model number wrong for radio variant | Medium | "Test CAT" button in setup wizard validates before saving. Clear error with link to Hamlib model list. |
| WSJT-X and Riglet both control same radio | Low | Each radio has a dedicated rigctld port. WSJT-X connects to its own port. No conflict by design. |
| Setup wizard unreachable on first boot | Low | avahi-daemon starts early. Fallback: document IP discovery via router DHCP table. |

---

## Architecture Decisions

| # | Topic | Decision |
|---|-------|----------|
| 1 | Frontend framework | **Svelte** — lightweight, no virtual DOM, well-suited for real-time canvas/WebSocket work |
| 2 | Authentication | **Session cookie** — signed cookies via `itsdangerous` or equivalent FastAPI middleware |
| 3 | FFT computation | **Dedicated asyncio daemon thread per radio** — each thread owns its PipeWire capture stream, runs numpy.fft, and feeds results into an `asyncio.Queue`; the WebSocket handler drains the queue and pushes JSON frames |
| 4 | rigctld polling interval | **100ms default**, configurable via `polling_interval_ms` in `config.yaml`; do not poll below ~50ms to avoid overwhelming radio CAT buffers |
| 5 | Static file serving | **FastAPI StaticFiles** to start (one-line, zero extra deps); Caddy can be added later as a layer in the rpi-image build to enable HTTPS/HTTP2 without code changes — avoid hardcoding `http://`, respect `X-Forwarded-Proto` |
| 6 | Config conflict error format | **RFC 7807 Problem Details** with `409 Conflict`; `errors` array identifies each conflict by type, field path, conflicting radio ID, and value |

### Config Validation

Config is modelled as **Pydantic models** — FastAPI already depends on Pydantic, so this is a zero-cost dependency. Benefits:
- Field-level type coercion and validation on both file load and `POST /api/config`
- Cross-radio uniqueness checks (duplicate serial ports, duplicate audio devices) via `@model_validator`
- Single source of truth: same models validate the YAML on disk and the API request body
- Pydantic `ValidationError` structure maps directly onto the RFC 7807 `errors` array format
