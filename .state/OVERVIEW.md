# Riglet -- System Overview

## What It Is

Riglet is a self-hosted web application that makes a ham radio operator's remote radios feel like transparent extensions of their operating desk. It runs on a Raspberry Pi 4 (64-bit) co-located with the radios, and presents a browser-based interface over the local LAN. No internet access is required or assumed.

The guiding principle is **"do one thing, do it well"**: Riglet is not a replacement for the radio or for desktop ham radio applications. It is an abstracted, generalized control surface and signal visualization tool that bridges the physical distance between the operator and the radio room. Operators who want to use WSJT-X, fldigi, or other software should be able to connect those applications through Riglet's virtual device passthrough, keeping the radio's identity and capabilities intact.

The target operator may have any number of radios (e.g., Icom IC-706mkiig, Yaesu FT-991A, Kenwood TS-590), each with its own USB audio interface. Each radio operates independently via its own tab.

## Problem Statement

Controlling amateur radios typically requires physical proximity to the equipment. Riglet decouples the operator from the radio room by exposing:

- **CAT control** with abstracted, generalized controls (frequency, mode, PTT, VFO, squelch, RF gain, CTCSS)
- **Audio streaming** (RX and TX) with client-side DSP capabilities
- **Rich signal visualization** (waterfall, spectrum scope, oscilloscope, and more)
- **Virtual device passthrough** so desktop apps can use the remote radio as if it were local

All of this is delivered through a browser UI accessible from anywhere on the LAN -- enabling remote operation from a laptop or desktop without proprietary software or internet dependency.

## Current State

The project has a working v0.1.0 implementation: FastAPI backend with config management, radio state/polling, CAT control, audio and waterfall WebSockets, device discovery, and a Svelte SPA with setup wizard, waterfall display, frequency/mode/band controls, PTT, S-meter, and audio controls.

The refocus described here expands the vision beyond v1's basic remote control into a richer, more capable operating environment.

---

## Design Philosophy

### Transparent Extension, Not Replacement

Riglet should feel like an extension cord for the radio, not a new radio. The controls are abstracted and generalized (not radio-model-specific knobs), but the radio's own character shows through. When the operator wants features their radio has natively, they should use the radio. When Riglet adds capabilities (like client-side DSP or advanced visualization), it should be clear these are Riglet features, not the radio's.

### Virtual Device Passthrough

A key architectural goal is enabling desktop applications to use remote radios as though they were locally connected:

- **Virtual serial port**: rigctld already supports remote TCP connections. Client-side applications (WSJT-X, fldigi, etc.) can connect to rigctld's TCP port directly or through a local `socat`/virtual serial mapping. Riglet documents and potentially automates this.
- **Virtual audio device**: A client-side companion utility (e.g., JACK, PipeWire, or a lightweight bridge daemon) can present Riglet's audio WebSocket as a local audio device, allowing desktop apps to use the remote radio's audio natively.

### Accessibility First

Accessibility is a first-class concern, not a retrofit. All controls must be keyboard-navigable, screen-reader-compatible, and respect user motion/contrast preferences from the outset.

---

## Architecture

### High-Level Topology

```
Browser (laptop/desktop on LAN)
  |-- SPA served as static files from FastAPI
  |-- REST API calls --> FastAPI backend
  |-- WebSocket connections (per radio):
        |-- Control WS:    bidirectional JSON (freq, mode, PTT, S-meter, SWR)
        |-- Audio WS:      bidirectional binary PCM (s16le, mono, 16kHz)
        |-- Waterfall WS:  server-->client JSON FFT frames (~10 fps)
  |-- Client-side DSP (Web Audio API)
  |-- Client-side volume, squelch, EQ, noise reduction

Raspberry Pi 4 (co-located with radios)
  |-- FastAPI backend (Python, uvicorn, port 8080)
  |-- rigctld x N (one Hamlib daemon per radio, ports 4532+)
  |-- PipeWire / pipewire-pulse (audio routing)
  |-- ser2net (raw serial forwarding for DigiLink)

Optional client-side companion
  |-- Virtual audio device bridge (JACK/PipeWire <-> WebSocket)
  |-- Virtual serial port (socat <-> rigctld TCP)
```

### Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| All radios always connected | rigctld runs as N permanent daemons. Tabs are independent viewports, not a shared resource. No teardown on tab switch. |
| No PTT interlock across radios | Simultaneous TX is the operator's responsibility. Antenna/RF planning is out of scope for software. |
| Single operator model | One WebSocket client per radio at a time. No multi-user concurrency. |
| REST for commands, WebSocket for streams | Freq/mode/PTT changes are REST POSTs. Audio, FFT, and state-push events use WebSocket. PTT via WebSocket is preferred for latency. |
| Simulation mode | A simulated radio is an explicit radio type in config. It generates fake signals (noise, tones, or mic input) for development and demonstration. An unreachable rigctld is simply an offline/error state -- not silently simulated. |
| Config-driven startup | Single YAML config. Changes require an explicit restart endpoint. |
| Client-side DSP | Audio processing (notch filter, bandpass, NR, compression, EQ) runs in the browser via Web Audio API. This leverages the client machine's CPU and avoids burdening the Pi. |
| Visualization is pluggable | Multiple visualization modes share the same FFT/audio data stream. The UI selects which renderer to use. |
| Virtual passthrough over integration | Instead of building WSJT-X/fldigi features into Riglet, expose virtual devices so those apps connect natively. |
| Scroll-wheel everywhere | All dial-type controls respond to scroll-wheel on hover for quick adjustment. |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, uvicorn |
| Dependency management | uv (replaces pip/venv directly) |
| Config validation | Pydantic v2 (zero-cost -- already a FastAPI dep) |
| Linting | Ruff |
| Type checking | mypy |
| Radio control | Hamlib (rigctld), one daemon per radio |
| Audio subsystem | PipeWire / pipewire-pulse, ALSA |
| Frontend | Svelte SPA (static files served by FastAPI) |
| Browser audio | Web Audio API AudioWorklet (PCM ring buffer); Opus fallback if latency exceeds 150ms |
| Client-side DSP | Web Audio API (BiquadFilterNode, DynamicsCompressorNode, custom AudioWorklets) |
| Serial/device | ser2net (DigiLink), pyserial (implicit), udev for hotplug |
| Service management | systemd (template units for rigctld, dedicated unit for FastAPI) |
| Discovery | Avahi / mDNS (riglet.local) |
| OS | Raspberry Pi OS Lite 64-bit (Bookworm) |
| Image build | rpi-image-gen |

---

## Signal Visualization

Riglet provides multiple visualization modes, all driven from the same audio/FFT data stream. The operator can toggle between them. A spectrum scope (frequency vs. amplitude) can optionally overlay any visualization mode.

### Visualization Modes

| Mode | Description | Axes |
|------|-------------|------|
| **Spectrogram (waterfall)** | Scrolling time-frequency display, color-mapped amplitude | Frequency (horizontal) vs. Time (vertical, scrolling down) |
| **Spectrum scope** | Real-time frequency response | Frequency (horizontal) vs. Amplitude (vertical) |
| **Oscilloscope** | Time-domain waveform | Time (horizontal) vs. Amplitude (vertical) |
| **Constellation / Goniometer** | X-Y plot comparing two audio channels (I/Q or L/R) | Channel 1 vs. Channel 2 |
| **Phase / Correlation meter** | Phase relationship between channels | Correlation coefficient display |
| **3D spectrogram** | Frequency-time-amplitude in perspective view | Frequency (horizontal), Time (depth), Amplitude (vertical) |
| **LUFS audio meter** | Real-time audio meter (Loudness Units Full Scale) | Perceived amplitude (vertical) |

### Optional Overlay Elements

- **LUFS audio meter**: User-toggleable panel. When enabled, displayed alongside the visualization area. Color-coded levels with a peak-hold bar that decays slowly so transient peaks remain visible.
- **Spectrum scope**: User-toggleable visualization mode. When selected, displayed as the primary visualization with color-coded levels.

### Waterfall Cursor

The waterfall (and potentially spectrum scope) includes a cursor that:

- Shows the current receive passband as a highlighted region, with the remainder dimmed
- Adapts width to the current mode's bandwidth (e.g., 2.4 kHz for SSB, 6 kHz for AM)
- Is draggable -- dragging the cursor changes the radio's frequency
- Has a centerline or sideline depending on the mode (center for AM/FM, edge for SSB)

### TX Visualization

When transmitting, the visualization switches to display the operator's own transmitted audio, providing visual feedback on signal quality and bandwidth.

---

## Data Flows

### 1. Radio Control (CAT)

```
Browser --> REST POST /api/radio/{id}/cat/freq --> FastAPI --> rigctld (TCP port) --> radio
Radio state change --> rigctld --> FastAPI polling --> Control WebSocket --> Browser
```

Both REST and WebSocket can be used for commands (freq, mode, PTT, nudge). WebSocket is preferred for PTT to minimize latency. The backend polls rigctld and pushes state changes (freq, mode, PTT, S-meter, SWR) to the Control WebSocket.

Extended CAT capabilities (where supported by Hamlib):
- **VFO control**: Multiple VFO awareness and switching
- **CTCSS/DCS tones**: Set and query subtone settings
- **SWR reading**: Query SWR meter when available
- **RF gain**: Adjust RF gain at the radio (where supported)

### 2. Audio (RX and TX)

```
RX: Radio --> USB audio interface --> PipeWire --> FastAPI --> Audio WebSocket (binary PCM) --> Browser AudioWorklet --> DSP chain --> speakers
TX: Browser mic --> DSP chain --> AudioWorklet --> Audio WebSocket (binary PCM) --> FastAPI --> PipeWire --> USB audio interface --> radio (only when PTT active)
```

Format: raw PCM, s16le, mono, 16 kHz, 20ms chunks (640 bytes each). TX audio sent while PTT is inactive is silently dropped.

#### Client-Side DSP Chain

Audio passes through a configurable processing chain in the browser (Web Audio API):

- **Volume control**: Client-side output level (independent of radio volume)
- **Squelch**: Client-side audio gate based on signal level
- **Bandpass filter**: Adjustable passband
- **Notch filter**: Remove specific interference frequencies
- **Noise reduction**: Spectral subtraction or similar
- **Compression**: Dynamics processing for TX audio
- **3-band EQ**: Bass/mid/treble adjustment for both RX and TX paths

The DSP chain applies to audio before output and can be toggled to be applied before visualization, so visualizations can reflect the processed signal when DSP is active.

### 3. Visualization Data

```
PipeWire audio capture --> FFT (server-side, 256 bins) --> Waterfall WebSocket (JSON, ~10 fps) --> Browser
Browser receives FFT + raw audio data --> selected visualization renderer --> canvas
```

The server sends FFT data for waterfall/spectrum views. Raw audio (already present via the Audio WebSocket) feeds the oscilloscope, constellation, and phase visualizations client-side.

### 4. Device Discovery and Hotplug

```
USB event --> udev --> Backend detection --> SSE stream (/api/devices/events)
                                         --> REST endpoints (/api/devices/serial, /api/devices/audio)
```

Frontend subscribes to SSE for live hotplug events. Disconnected devices are flagged but not auto-cleared from config.

### 5. Setup and Config Flow

**First boot / missing config file**: `GET /api/status` returns `setup_required: true`. The SPA redirects to the setup wizard. On completion the wizard writes config and restarts services; the SPA enters a reconnect loop and then navigates to the main UI.

**Config file exists, no radios configured**: The main UI loads normally. No radio panels are shown. A persistent config/setup button is always visible, allowing the operator to enter the setup wizard at any time.

**Config change and service restart**:
```
UI --> POST /api/config (validate + write) --> POST /api/config/restart
  1. Check no radio has PTT active (409 if any does)
  2. Push service_restart event to all WebSocket clients
  3. Write new .env files from config
  4. systemctl restart rigctld@* and riglet
  5. Client enters reconnect loop (polls /api/status every 1s, 30s timeout)
```

---

## UI Design

### Layout and Configurability

The display layout is fully configurable:

- **Default layouts** ship with the application for common use cases (voice operating, digital modes, SWL)
- **Custom layouts** can be created, saved, exported, and imported -- treated as first-class citizens alongside defaults
- The operator chooses which visualizations are visible, their arrangement, and their relative sizes

### Controls

- **Frequency display**: Large monospace readout with nudge buttons. Scroll-wheel adjustable on hover.
- **Mode selector**: Only shows modes relevant to the radio's capabilities. Irrelevant/exotic modes are hidden by default.
- **Band selector**: Band pills for all amateur bands available in the operator's configured region. Pills for bands not enabled in the radio's config are shown greyed out and non-interactive.
- **Frequency presets**: Per-band named presets storing frequency, offset, and CTCSS tone. Selecting a preset tunes the radio and displays the preset label in the frequency display. Presets can be imported and exported.
- **PTT button**: Large, prominent. Supports VOX mode with configurable hang time and hot-mic prevention (audio gate threshold before VOX engages).
- **Frequency dial**: Allow the frequency to be tuned manually with a dial. Scroll-wheel on hover.
- **Volume dial**: Client-side browser audio level. Scroll-wheel on hover.
- **Squelch dial**: Client-side audio squelch. Scroll-wheel on hover.
- **RF gain**: Where radio supports remote adjustment via Hamlib; otherwise client-side gain control.
- **All dials**: Respond to scroll-wheel on hover for quick adjustment.

### Theming

- Light mode and dark mode, switchable by the operator
- Respects `prefers-color-scheme` system preference as default

### Accessibility

- Full keyboard navigation for all controls
- ARIA labels and roles on all interactive elements
- Screen reader compatibility for frequency, mode, meter readings
- Respect `prefers-reduced-motion` for animations (waterfall scroll, meter transitions)
- Sufficient contrast ratios in both light and dark themes

---

## Simulation Mode

Simulation is an explicit radio type, not an automatic fallback. A simulated radio is configured just like a real radio, but with `type: simulated` instead of hardware references.

- Generates fake audio signals: noise, tones, or the host machine's microphone input as a signal source
- Useful for UI development, demonstrations, and testing without any radio hardware
- An unreachable rigctld on a real radio is an error/offline state -- it does not silently fall back to simulated behavior

---

## Config Schema

Single source of truth: `~/.config/riglet/config.yaml` (dev), `/etc/riglet/config.yaml` (production). The `RIGLET_CONFIG` env var overrides both.

Top-level sections: `operator` (callsign, grid, region), `network` (hostname, port), `audio` (sample rate, chunk size), `radios` (array of radio definitions), `presets` (frequency presets, stored separately from radio config).

**`operator.region`**: Selects the regulatory band plan. Known regions: `us` (FCC/ARRL), `eu` (IARU Region 1), `au` (IARU Region 3 / WIA). Defaults to `us`. Determines the full set of available bands shown in the UI, including HF (160m–10m), VHF (6m, 2m), and UHF (70cm) where applicable.

Each radio entry contains: id, name, type (real | simulated), hamlib_model, serial_port, baud_rate, ptt_method, audio_source, audio_sink, rigctld_port, enabled, polling_interval_ms, bands (list of enabled band names from the region's band plan, e.g. `["160m", "80m", "40m", "20m", "15m", "10m", "2m", "70cm"]`).

Each preset entry contains: id, name (display label), band, frequency_mhz, offset_mhz (optional, for repeaters), ctcss_tone (optional), mode (optional override).

Validation rules:
- Serial ports must be unique across radios
- Audio source/sink pairs must be unique across radios
- Disabled radios may have empty audio fields
- Bands listed for a radio must exist in the configured region's band plan
- Config is read at startup only; runtime changes require explicit restart

---

## File Structure

```
riglet/
  deployment/                     # Raspberry Pi image build
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
    deps.py                       # Shared FastAPI dependencies
    devices.py                    # serial + audio device discovery, SSE hotplug
    pyproject.toml                # dependencies, ruff + mypy config
    routers/
      system.py                   # /api/status, /api/config, /api/logs
      devices.py                  # /api/devices/*
      cat.py                      # /api/radio/{id}/cat/*
      audio.py                    # /api/radio/{id}/audio/* + audio WS
      waterfall.py                # /api/radio/{id}/ws/waterfall

  ui/                             # Svelte SPA
    src/
      routes/
        +page.svelte              # Main UI (radio control + visualization)
        setup/+page.svelte        # Setup wizard
      lib/
        api.ts                    # Typed REST client
        websocket.ts              # Control WebSocket with reconnect
        reconnect.ts              # Restart polling utility
        audio/                    # AudioManager, PCM worklet processor
        components/               # UI components (waterfall, controls, meters)
        components/wizard/        # Setup wizard step components
```

---

## Deployment Model

- **Image-based**: A custom Raspberry Pi OS image is built with rpi-image-gen, flashed to SD card
- **First boot**: If no config file exists, the backend serves the setup wizard at port 8080. If a config file exists with no radios, the main UI loads with a setup button.
- **mDNS**: avahi-daemon advertises `riglet.local` immediately on boot
- **User**: All services run as the `ham` user (groups: dialout, audio, plugdev)
- **Python**: Dependencies managed with uv; virtual environment at `/opt/riglet/venv`
- **App location**: `/opt/riglet/app/`

---

## Future Hardware: Riglet Snout

A companion hardware accessory concept for the desk side:

- Large main tuning dial (rotary encoder, high resolution)
- Several small auxiliary dials (volume, squelch, RF gain)
- Toggle switches (mode, VFO, band)
- PTT switch/button
- Communicates with the browser via WebHID, Web Serial, or WebUSB
- DIY-constructible with published designs, potentially also sold pre-built

This is a future exploration, not part of the current software scope, but the UI control architecture should be designed to accept input from arbitrary sources (keyboard, mouse, touch, hardware controller) without special-casing.

---

## v0.1.0 Definition of Done (Completed)

v0.1.0 delivered:

1. Fresh SD card image boots a Pi 4 and `riglet.local:8080` is reachable within 60 seconds
2. One radio (IC-706mkiig) connected via USB; setup wizard detects it, assigns audio, passes CAT test
3. Main UI shows: live waterfall (~10 fps), correct frequency, working frequency/mode controls, RX audio in browser, PTT + TX audio from browser mic
4. Config changes persist across Pi reboot

## v0.2.0 Goals

Building on v0.1.0, v0.2.0 expands Riglet into its full vision:

1. **Multiple visualization modes**: Spectrum scope, oscilloscope, constellation diagram, phase meter, 3D spectrogram (waterfall already exists)
2. **LUFS audio metering** with peak hold (user-toggleable panel)
3. **Waterfall cursor**: Mode-aware passband overlay, draggable for frequency tuning
4. **Client-side DSP**: Notch filter, bandpass, noise reduction, compression, 3-band EQ
5. **Client-side volume and squelch controls**
6. **TX visualization**: Show transmitted audio in the active visualization
7. **Configurable layouts**: Save/load/export/import display configurations
8. **Light/dark theme** with system preference detection
9. **Accessibility**: Full keyboard navigation, ARIA, screen reader support
10. **Scroll-wheel on all dials**
11. **Enhanced simulation**: Configurable simulated radios with generated signals
12. **Extended CAT**: VFO switching, SWR meter, CTCSS tone control
13. **VOX mode** with hot-mic prevention
14. **Curated mode list**: Hide irrelevant modes per radio
15. **Virtual device passthrough**: Document and where possible automate virtual serial port and virtual audio device setup so desktop apps (WSJT-X, fldigi) can use the remote radio natively
16. **Region-aware band plan**: Operator selects a region (US, EU, AU) which determines available bands including VHF/UHF (2m, 70cm); per-radio band config selects from those
17. **Frequency presets (memory channels)**: Named per-band presets storing frequency, offset, CTCSS, and mode; label shown in frequency display when active; import/export as JSON

### Explicitly Out of Scope for v0.2.0

- Multi-user / shared operation
- Internet remote access (outside LAN)
- Mobile app
- Logging / QSO database integration
- Riglet Snout hardware
- Hardware dial integration (design for it, but do not implement)

---

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| PipeWire device names change between reboots | Medium | Match devices by USB VID/PID, not full device string. Store VID/PID in config alongside device name. |
| Audio latency unacceptable over LAN | Low | Prototype audio pipeline first. Fallback to Opus encoding if raw PCM exceeds 150ms. |
| rigctld model number wrong for radio variant | Medium | "Test CAT" button in setup wizard validates before saving. Clear error with link to Hamlib model list. |
| WSJT-X and Riglet both control same radio | Low | Each radio has a dedicated rigctld port. WSJT-X connects to its own port. No conflict by design. |
| Setup wizard unreachable on first boot | Low | avahi-daemon starts early. Fallback: document IP discovery via router DHCP table. |
| Client-side DSP performance varies | Medium | Web Audio API is hardware-accelerated on most browsers. Provide a "disable DSP" toggle. Test on low-end hardware. |
| 3D spectrogram WebGL performance on low-end clients | Medium | Use lightweight WebGL (e.g., Three.js or raw WebGL2). Provide a fallback 2D mode. Test on integrated GPUs. |
| VOX hot-mic in noisy environments | Medium | Require an audio gate threshold before VOX engages. Make threshold configurable. Default to PTT-only mode. |
| Browser scroll-wheel hijacking page scroll | Low | Only capture scroll events when pointer is directly over a dial control. Use passive event listeners elsewhere. |

---

## Architecture Decisions

| # | Topic | Decision |
|---|-------|----------|
| 1 | Frontend framework | **Svelte** -- lightweight, no virtual DOM, well-suited for real-time canvas/WebSocket work |
| 2 | FFT computation | **Dedicated asyncio daemon thread per radio** -- each thread owns its PipeWire capture stream, runs numpy.fft, and feeds results into an `asyncio.Queue`; the WebSocket handler drains the queue and pushes JSON frames |
| 3 | rigctld polling interval | **100ms default**, configurable via `polling_interval_ms` in `config.yaml`; do not poll below ~50ms to avoid overwhelming radio CAT buffers |
| 4 | Static file serving | **FastAPI StaticFiles** to start (one-line, zero extra deps); Caddy can be added later as a layer in the rpi-image build to enable HTTPS/HTTP2 without code changes |
| 5 | Config conflict error format | **RFC 7807 Problem Details** with `409 Conflict`; `errors` array identifies each conflict by type, field path, conflicting radio ID, and value |
| 6 | Client-side DSP | **Web Audio API** -- BiquadFilterNode for filters/EQ, DynamicsCompressorNode for compression, custom AudioWorklets for noise reduction and squelch. Runs entirely in browser, no Pi CPU cost. |
| 7 | Visualization architecture | **Pluggable renderers** -- all visualization modes receive the same data (FFT bins + raw PCM). A renderer interface allows adding new visualizations without changing the data pipeline. |
| 8 | Layout system | **JSON-serializable layout configs** -- each layout is a JSON document describing which components are visible and their arrangement. Stored in browser localStorage and optionally exported as files. |
| 9 | Input abstraction | **Event-driven control model** -- controls respond to abstract "change" events, not specific input devices. This allows keyboard, mouse scroll, touch, and future hardware controllers to drive the same controls. |

### Config Validation

Config is modelled as **Pydantic models** -- FastAPI already depends on Pydantic, so this is a zero-cost dependency. Benefits:
- Field-level type coercion and validation on both file load and `POST /api/config`
- Cross-radio uniqueness checks (duplicate serial ports, duplicate audio devices) via `@model_validator`
- Single source of truth: same models validate the YAML on disk and the API request body
- Pydantic `ValidationError` structure maps directly onto the RFC 7807 `errors` array format
