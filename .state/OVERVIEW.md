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
| Single operator model | One WebSocket client per radio at a time. A new connection forcibly closes the previous one without notification. No multi-user concurrency. This is an intentional simplification, but the displaced client receives no explanation for the disconnection (see Known Limitations). |
| REST for commands, WebSocket for streams | Freq/mode/PTT changes are REST POSTs. Audio, FFT, and state-push events use WebSocket. PTT via WebSocket is preferred for latency. |
| Simulation mode | A simulated radio is an explicit radio type in config. It generates fake signals (noise, tones, or mic input) for development and demonstration. An unreachable rigctld is simply an offline/error state -- not silently simulated. |
| Config-driven startup | Single YAML config. Changes require an explicit restart endpoint. |
| Client-side DSP | Audio processing (notch filter, bandpass, NR, compression, EQ) runs in the browser via Web Audio API. This leverages the client machine's CPU and avoids burdening the Pi. |
| Visualization is pluggable | Multiple visualization modes share the same FFT/audio data stream. The UI selects which renderer to use. |
| Virtual passthrough over integration | Instead of building WSJT-X/fldigi features into Riglet, expose virtual devices so those apps connect natively. |
| Scroll-wheel everywhere | All dial-type controls respond to scroll-wheel on hover for quick adjustment. |

---

## Security Model

### Authentication Design: Session-Cookie Password Auth

Riglet uses a single shared password to protect the entire application. There are no user accounts, roles, or registration -- just one password that grants full access. This is appropriate for a single-operator, LAN-only deployment where the operator is the only person who should be controlling the radio.

#### Threat Model

Even on a private LAN, unauthenticated access creates real risk:

- Any device on the network can key the transmitter (FCC regulatory implications for unauthorized transmission)
- Configuration can be overwritten or corrupted by any LAN client
- Service restarts can be triggered arbitrarily, disrupting active operation

#### Password Storage

The password hash is stored in a **separate secrets file** at `~/.config/riglet/secrets.yaml` (dev) or `/etc/riglet/secrets.yaml` (production), respecting a `RIGLET_SECRETS` environment variable override. Rationale for keeping it separate from `config.yaml`:

- The config file is exported, imported, and displayed in the UI. A password hash in config risks accidental exposure.
- The secrets file has a focused responsibility and can have tighter filesystem permissions (mode 0600).
- The config schema remains clean -- no auth fields mixed into `RigletConfig`.

The secrets file schema:

```yaml
password_hash: "$2b$12$..."    # bcrypt hash of the password
session_secret: "..."           # 32-byte random key for signing session cookies (hex-encoded)
```

**Password hashing uses `bcrypt`** via the `bcrypt` Python package. bcrypt is the right choice here: it is purpose-built for password hashing, has a built-in salt, and is computationally expensive enough to resist brute-force attacks even if the hash leaks. The work factor (cost=12, the default) is appropriate for a single login on a Pi 4.

The `session_secret` is a 32-byte random key generated once and used to sign session cookies via `itsdangerous.URLSafeTimedSerializer`. This key is never exposed to the client.

#### Password Setting

The password is set during the **setup wizard** as a new step (Step 5, before Review & Apply). On first boot (no secrets file exists), the wizard requires the operator to choose a password. The password has a minimum length of 8 characters but no complexity requirements -- this is a LAN device, not a bank.

After initial setup, the password can be changed via a `POST /api/auth/password` endpoint (requires current session). A `RIGLET_DEFAULT_PASSWORD` environment variable can seed the password on first boot for headless/automated deployments, but is ignored if a secrets file already exists.

If the secrets file is deleted, the next startup regenerates the session secret (invalidating all sessions) and the setup wizard prompts for a new password.

#### Session Mechanism

Sessions use **signed, HttpOnly cookies** rather than Bearer tokens or JWTs. Rationale:

| Approach | Pros | Cons |
|----------|------|------|
| HttpOnly cookie | Browser sends automatically (no JS token management); immune to XSS token theft; works with WebSocket upgrades transparently | Requires CSRF protection for mutating requests |
| Bearer token in localStorage | Simple to implement; explicit in API calls | Vulnerable to XSS; requires manual attachment to every request and WebSocket URL |
| JWT | Stateless verification | Overkill for single-user; no revocation without server state; token size overhead |

**Decision: HttpOnly session cookie**, signed with `itsdangerous.URLSafeTimedSerializer`.

Cookie properties:
- **Name**: `riglet_session`
- **Value**: `itsdangerous`-signed payload containing `{"v": 1}` (version marker; no user identity needed since there is only one user)
- **HttpOnly**: `true` (JavaScript cannot read the cookie -- XSS cannot steal the session)
- **SameSite**: `Lax` (cookie sent on same-site requests and top-level navigations; blocks cross-site POST attacks without breaking normal navigation)
- **Secure**: `false` (Riglet runs on HTTP over LAN; setting Secure would break cookies entirely)
- **Max-Age**: 30 days (sessions last 30 days; configurable via `SESSION_MAX_AGE_DAYS` env var)
- **Path**: `/`

**CSRF protection**: Because SameSite=Lax already blocks cross-origin POST/PUT/DELETE/PATCH requests from other sites, and the application runs on a private LAN (not a public domain), explicit CSRF tokens are not required. The combination of SameSite=Lax + HttpOnly provides sufficient protection for this deployment model.

Session validation: On each request, the middleware unsigns the cookie using `itsdangerous`. If the signature is invalid or the cookie has expired (older than Max-Age), the request is treated as unauthenticated. There is no server-side session store -- the signed cookie is the session.

#### Backend Enforcement

Authentication is enforced via **Starlette middleware** (`server/auth.py:AuthMiddleware`) rather than per-router FastAPI dependencies. Middleware is the right choice because:

- It catches every request in one place, including WebSocket upgrades
- No risk of forgetting to add a dependency to a new router
- Public endpoints are whitelisted explicitly (deny-by-default)

**Public endpoints** (no session required):
- `POST /api/auth/login` -- the login endpoint itself
- `GET /api/status` -- needed for health checks, setup wizard restart polling, and determining `setup_required` / `auth_required` state
- `GET /` and all static file paths (`*.js`, `*.css`, `*.html`, `*.svg`, `*.png`, etc.) -- SPA assets must load without auth so the login page can render
- `GET /api/hamlib/models` -- needed by setup wizard before auth exists

**All other endpoints** require a valid `riglet_session` cookie. Unauthenticated requests receive a `401 Unauthorized` JSON response: `{"detail": "Authentication required"}`.

**Setup wizard exception**: When no password has been set yet (secrets file missing or `password_hash` empty), the middleware permits all requests without authentication. This allows the setup wizard to run on first boot. Once a password is set and the secrets file exists, all subsequent requests require auth. The `GET /api/status` response includes an `auth_required: false` flag in this state so the frontend knows not to show the login gate.

**WebSocket auth**: WebSocket upgrade requests carry cookies automatically (the browser sends cookies for the upgrade HTTP request). The middleware checks the cookie on the upgrade request just like any other request. No query-parameter tokens needed. This is a key advantage of the cookie approach over Bearer tokens.

#### Frontend Flow

The frontend implements a **login gate** at the `+layout.svelte` level:

1. On app load, `GET /api/status` is called. The response includes `auth_required: boolean`.
2. If `auth_required` is `false` (first boot, no password set), the app proceeds normally to the setup wizard or main UI.
3. If `auth_required` is `true`, the layout checks for an existing valid session by looking at the status response. If the request succeeded with a 200 (cookie was sent and accepted), the user is authenticated.
4. If the user needs to log in (no cookie or expired cookie), the layout renders a `/login` route instead of the requested page.
5. The login page has a single password field and a submit button. On submit, it calls `POST /api/auth/login` with `{"password": "..."}`.
6. On success, the server sets the `riglet_session` cookie in the response, and the frontend navigates to `/` (or the originally requested path).
7. On failure, the login page shows an error: "Incorrect password."
8. If any API call returns 401 during normal operation (session expired), the frontend redirects to the login page.

The login page is a new SvelteKit route at `ui/src/routes/login/+page.svelte`. It is styled consistently with the setup wizard (dark background, centered card, Riglet branding).

The `api.ts` `request()` helper is updated to detect 401 responses and trigger a redirect to `/login` via `goto('/login')`. The `credentials: 'same-origin'` fetch option ensures cookies are sent with every request (this is the default for same-origin requests but is set explicitly for clarity).

#### Logout

A logout button is added to the topbar (visible when authenticated). Clicking it calls `POST /api/auth/logout`, which clears the `riglet_session` cookie by setting it with `Max-Age=0`. The frontend then redirects to `/login`.

#### Password Change

A "Change Password" option is accessible from the setup/settings page. It calls `POST /api/auth/password` with `{"current_password": "...", "new_password": "..."}`. On success, all existing sessions are invalidated (the `session_secret` is regenerated in the secrets file), and the user is redirected to the login page with a message: "Password changed. Please log in with your new password."

#### Dependencies

Two new Python packages:
- **`bcrypt`**: Password hashing. Well-established, minimal, no transitive dependencies.
- **`itsdangerous`**: Cookie signing. Already was planned as a dependency; lightweight, from the Pallets project (Flask ecosystem).

Both are added to `pyproject.toml` `dependencies`.

#### Architecture Decision Record

| # | Topic | Decision | Rationale |
|---|-------|----------|-----------|
| 14 | Auth mechanism | **HttpOnly session cookie** (signed with itsdangerous) | Automatic browser handling; XSS-immune; works with WebSocket upgrades transparently; simpler frontend code than Bearer tokens |
| 15 | Password storage location | **Separate secrets file** (`secrets.yaml`) | Keeps password hash out of exportable config; tighter file permissions; clean separation of concerns |
| 16 | Password hashing | **bcrypt** (cost=12) | Purpose-built for passwords; built-in salt; appropriate for single-login Pi 4 workload |
| 17 | Auth enforcement | **Starlette middleware** (deny-by-default) | Catches all routes including WebSocket; no risk of missing a router; whitelist is explicit |
| 18 | Session duration | **30 days** | Long enough for daily use without re-login; short enough to limit exposure from a stolen cookie |
| 19 | CSRF protection | **SameSite=Lax** (no explicit CSRF tokens) | SameSite blocks cross-origin mutations; LAN-only deployment eliminates external attacker surface |
| 20 | Password initial setup | **Setup wizard step** | Natural place for first-time configuration; consistent with existing setup flow |

### Input Validation Gaps

Several user-supplied values are passed through to system interfaces without adequate validation:

1. **rigctld command injection**: Mode strings from the API are interpolated directly into rigctld protocol commands. The rigctld protocol is newline-delimited, so a mode value containing `\n` could inject additional commands (e.g., activating PTT). Mode strings must be validated against the radio's known mode list before being sent to rigctld.

2. **Radio ID format**: Radio IDs are used in filesystem paths (env file writes) and systemd unit names without format validation. A crafted ID containing path traversal characters (e.g., `../../tmp/evil`) could write files to arbitrary locations. The `RadioConfig.id` field needs a Pydantic validator restricting it to safe characters (e.g., `^[a-z0-9_-]+$`).

3. **Env file content injection**: Config values like `serial_port` are written directly into systemd environment files. Values containing newlines could inject additional environment variables. String format validation is needed on all config fields that are written to env files.

4. **Audio device names**: Audio source/sink names from config are passed as subprocess arguments to `pw-record` and `pw-play`. While `create_subprocess_exec` prevents shell injection, the values should still be validated against known device names.

5. **Frequency bounds**: The `set_freq` endpoint accepts any float value without consulting the band plan data that exists in `bandplan.py`. Negative values, zero, or out-of-band frequencies are passed through to the radio.

### Deployment Hardening Notes

The deployment script (`deployment/scripts/01-configure.sh`) explicitly enables SSH password authentication. For an embedded device on a home network, key-based-only authentication would be more appropriate. This is a deployment configuration issue, not a code issue, but it affects the overall security posture.

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

#### Client-Side DSP Chains (v0.3.0)

Two independent DSP chains per radio, both running in the browser via Web Audio API:

**RX Chain** (between PCM worklet output and speakers):
- High-pass filter (100-300 Hz configurable)
- Low-pass filter (2500-3500 Hz configurable)
- Bandpass filter (presets: Voice/CW/SSB/AM/Custom)
- Notch filter (manual center/width)
- Audio peak filter (narrow peaking EQ, high Q)
- Noise blanker (impulse noise removal, AudioWorklet)
- Noise reduction (Wiener filter, AudioWorklet)
- Dynamics compressor
- 3-band EQ (bass/mid/treble shelving)
- Squelch gate
- Volume control

**TX Chain** (between microphone source and PCM worklet input):
- High-pass filter (100-300 Hz, default 200 Hz)
- Low-pass filter (2500-3500 Hz, default 2800 Hz)
- 3-band EQ (bass/mid/treble, mid-boost default)
- Vocal compressor (presets: Mild/Moderate/Heavy/Manual)
- Limiter (hard ceiling, auto-enabled with compressor)
- Noise gate (configurable threshold, integrates with VOX)

DSP settings are persisted per-radio in the backend config YAML and loaded on page init.

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
    auth.py                       # AuthMiddleware, password hashing, secrets file I/O
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
        audio/                    # AudioManager, PCM worklet, DSP chains
          audio-manager.ts        # AudioContext lifecycle, chain wiring
          dsp-chain.ts            # RxDspChain (v0.3.0: extended with HPF, LPF, peak, NB)
          tx-dsp-chain.ts         # TxDspChain (v0.3.0: new TX processing chain)
          pcm-worklet-processor.js # s16le ring buffer worklet
          nr-worklet.js           # Noise reduction AudioWorklet
          nb-worklet.js           # Noise blanker AudioWorklet (v0.3.0)
          noise-gate-worklet.js   # TX noise gate AudioWorklet (v0.3.0)
          vox.ts                  # VOX detector
          lufs.ts                 # LUFS metering
        components/               # UI components (waterfall, controls, meters)
        components/dsp/           # DSP UI components (v0.3.0)
          RxDspPillRow.svelte     # Pill row container for RX DSP
          DspPill.svelte          # Generic toggle pill
          DspPopover.svelte       # Generic config popover
          HighpassConfig.svelte   # HPF config controls
          LowpassConfig.svelte    # LPF config controls
          BandpassConfig.svelte   # BP preset + custom config
          NotchConfig.svelte      # Notch filter config
          PeakFilterConfig.svelte # Peak filter config
          NoiseBlankerConfig.svelte # NB config
          NrConfig.svelte         # NR config
          CompressorConfig.svelte # Compressor config
          EqConfig.svelte         # 3-band EQ config
          TxDspMenu.svelte        # TX DSP modal/slide-out
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

## v0.3.0 Goals -- Per-Radio DSP Chains

v0.3.0 replaces the existing single-purpose RX DSP chain with a fully independent, per-radio dual-chain DSP architecture: one chain for the microphone (TX) path and one for the receive (RX) path. Each radio gets its own pair of chains. DSP settings are persisted per-radio so they survive page reloads.

### Problem Statement

v0.2.0 delivered a basic RX-only DSP chain (bandpass, notch, NR, compressor, 3-band EQ). This is insufficient for serious operating:

1. **No TX audio processing.** Operators need highpass/lowpass filtering, EQ, compression/limiting, and a noise gate on their microphone signal before it reaches the radio. Without this, transmitted audio quality depends entirely on the raw microphone, which is rarely acceptable.
2. **The RX chain is missing several standard receiver DSP features**: audio peak filter, noise blanker (for AC/ground hum), and preset-based bandpass configurations (2.4 kHz voice, 500 Hz CW, etc.).
3. **DSP settings are not persisted.** Every page reload resets all DSP controls to defaults.
4. **The UI for DSP controls does not match the operational workflow.** RX DSP controls should be immediately accessible as compact pills below the frequency display. TX DSP controls should be co-located with the PTT button and accessed via a configuration menu.

### Architecture: Where DSP Processing Happens

All DSP runs client-side in the browser via the Web Audio API. This is the correct choice for Riglet because:

- The Raspberry Pi 4 has limited CPU headroom; offloading DSP to the operator's browser machine (laptop/desktop) is free.
- Web Audio API provides hardware-accelerated BiquadFilterNode, DynamicsCompressorNode, and the AudioWorklet API for custom processors -- all at audio-thread priority with deterministic timing.
- Latency is minimal: Web Audio nodes process in 128-sample render quanta (~8ms at 16 kHz), well within the acceptable range.

**Decision: No backend changes for DSP processing.** The backend continues to send/receive raw PCM. All filtering, EQ, compression, gating, and noise reduction happen in browser Web Audio graphs.

**Decision: DSP settings persistence via backend config.** Settings are saved to the backend config YAML (per-radio `dsp` section) rather than localStorage. This ensures settings survive browser changes, incognito mode, and multi-device access. A debounced save (500ms after last change) prevents hammering the config endpoint during rapid adjustment. The frontend holds working state; the backend is the durable store.

### DSP Chain Architecture

#### RX Chain (Receive Path)

Signal flow (unchanged entry point -- PCM from WebSocket feeds the existing AudioWorklet):

```
PCM worklet output -> highpass -> lowpass -> bandpass -> notch -> peak_filter -> noise_blanker -> NR -> compressor -> bass_eq -> mid_eq -> treble_eq -> squelch_gate -> volume_gain -> destination
```

New nodes added to the existing `DspChain` class:
- **High-pass filter** (BiquadFilterNode, type: highpass) -- configurable 100-300 Hz cutoff
- **Low-pass filter** (BiquadFilterNode, type: lowpass) -- configurable 2500-3500 Hz cutoff
- **Audio peak filter** (BiquadFilterNode, type: peaking, high Q) -- narrow peak to pull a signal out of noise
- **Noise blanker** (custom AudioWorklet) -- detects and blanks impulse noise from AC hum, motor noise, etc. Uses a threshold-based sample replacement algorithm.
- **Bandpass presets** -- not a new node, but preset configurations that set highpass + lowpass + bandpass in one click: "2.4 kHz Voice", "500 Hz CW", "2.7 kHz SSB", "6 kHz AM", "Custom"

The existing bandpass, notch, NR, compressor, and 3-band EQ nodes remain as-is but are repositioned in the chain as shown above.

#### TX Chain (Transmit Path -- New)

Signal flow (mic capture feeds into this chain before PCM encoding):

```
mic_source -> highpass -> lowpass -> bass_eq -> mid_eq -> treble_eq -> compressor -> limiter -> noise_gate -> tx_pcm_worklet
```

The TX chain is a new `TxDspChain` class, structurally similar to `DspChain` but with different defaults and different nodes:

- **High-pass filter** (BiquadFilterNode, type: highpass) -- configurable 100-300 Hz, default 200 Hz. Removes breath pops, handling rumble.
- **Low-pass filter** (BiquadFilterNode, type: lowpass) -- configurable 2500-3500 Hz, default 2800 Hz. Removes hiss and keeps signal within radio bandwidth.
- **3-band equalizer** (3x BiquadFilterNode: lowshelf, peaking, highshelf) -- same structure as RX EQ but with TX-oriented defaults (slight mid boost for intelligibility).
- **Vocal compressor** (DynamicsCompressorNode) -- with presets:
  - "Mild": ratio 2:1, threshold -20 dB, attack 10ms, release 200ms
  - "Moderate": ratio 4:1, threshold -24 dB, attack 3ms, release 150ms
  - "Heavy": ratio 8:1, threshold -30 dB, attack 1ms, release 100ms
  - "Manual": all parameters user-adjustable (ratio, threshold, attack, release)
- **Limiter** (DynamicsCompressorNode with ratio 20:1, threshold -3 dB, attack 0.1ms, release 50ms) -- hard ceiling to prevent clipping/overmodulation. Always active when compressor is enabled.
- **Noise gate** (custom AudioWorklet or gain node with RMS threshold detection) -- configurable threshold in dBFS. When mic signal is below threshold, output is muted. Essential for VOX operation to prevent ambient noise from keying the transmitter. Integrates with the existing VoxDetector: the noise gate threshold should be at or below the VOX threshold.

**Key design decision: The TX chain processes audio before it reaches the PCM worklet for encoding.** Currently, the mic MediaStreamSource connects directly to the PCM worklet's input. With the TX chain, the connection becomes:

```
mic_source -> TxDspChain.input ... TxDspChain.output -> pcm_worklet (input)
```

The PCM worklet's TX capture path then encodes the already-processed audio.

#### Web Audio Graph Integration

The current audio graph is:

```
[PCM worklet] ---output---> [DspChain] -> [squelch] -> [volume] -> [speakers]
[mic source] ---input----> [PCM worklet] (TX capture in worklet)
```

The v0.3.0 graph becomes:

```
RX: [PCM worklet] ---output---> [RxDspChain] -> [squelch] -> [volume] -> [speakers]
TX: [mic source] -> [TxDspChain] ---output---> [PCM worklet] (TX capture in worklet)
```

Both chains are instantiated per-radio by `AudioManager`. `AudioManager.startRx()` builds the RX chain (as it does today, with additional nodes). `AudioManager.startTx()` builds the TX chain and inserts it between the mic source and the worklet node.

### Config Schema Additions

Add a `dsp` field to `RadioConfig` in `server/config.py`:

```python
class RxDspConfig(BaseModel):
    highpass_enabled: bool = False
    highpass_hz: int = 200          # 100-300
    lowpass_enabled: bool = False
    lowpass_hz: int = 3000          # 2500-3500
    bandpass_enabled: bool = False
    bandpass_preset: str = "voice"  # "voice", "cw", "ssb", "am", "custom"
    bandpass_center_hz: int = 1500  # only used when preset is "custom"
    bandpass_width_hz: int = 2400   # only used when preset is "custom"
    notch_enabled: bool = False
    notch_center_hz: int = 1000
    notch_width_hz: int = 50
    peak_filter_enabled: bool = False
    peak_filter_hz: int = 800
    peak_filter_q: float = 10.0
    noise_blanker_enabled: bool = False
    noise_blanker_threshold: float = 0.5  # 0.0-1.0
    nr_enabled: bool = False
    nr_amount: float = 0.5
    compressor_enabled: bool = False
    compressor_threshold_db: float = -24.0
    compressor_ratio: float = 4.0
    eq_enabled: bool = False
    bass_gain_db: float = 0.0
    mid_gain_db: float = 0.0
    treble_gain_db: float = 0.0

class TxDspConfig(BaseModel):
    highpass_enabled: bool = True
    highpass_hz: int = 200          # 100-300
    lowpass_enabled: bool = True
    lowpass_hz: int = 2800          # 2500-3500
    eq_enabled: bool = False
    bass_gain_db: float = 0.0
    mid_gain_db: float = 2.0       # slight mid boost default
    treble_gain_db: float = 0.0
    compressor_enabled: bool = False
    compressor_preset: str = "moderate"  # "mild", "moderate", "heavy", "manual"
    compressor_threshold_db: float = -24.0
    compressor_ratio: float = 4.0
    compressor_attack_ms: float = 3.0
    compressor_release_ms: float = 150.0
    limiter_enabled: bool = False   # auto-enabled with compressor
    noise_gate_enabled: bool = False
    noise_gate_threshold_db: float = -50.0

class DspConfig(BaseModel):
    rx: RxDspConfig = RxDspConfig()
    tx: TxDspConfig = TxDspConfig()
```

`RadioConfig` gets a new field: `dsp: DspConfig = DspConfig()`.

A new REST endpoint `POST /api/radio/{id}/dsp` accepts partial DSP config updates and saves them to the config file (debounced server-side or client-side). `GET /api/radio/{id}/dsp` returns the current DSP config for a radio.

### Frontend Component Plan

#### RX DSP Controls -- Pill Row Below Frequency Display

The RX DSP controls appear as a horizontal row of compact pill buttons directly below the frequency display (inside the same layout panel). Each pill represents one DSP feature:

```
[ HPF ] [ LPF ] [ BP: Voice ] [ Notch ] [ Peak ] [ NB ] [ NR ] [ Comp ] [ EQ ]
```

Pill behavior:
- **Inactive**: dark background, dim text
- **Active**: colored background (blue for filters, green for NR, orange for compression), bright text
- **Click**: toggles the feature on/off
- **Click when active** (or right-click / long-press): opens a configuration popover/dropdown with the feature's parameters and an explicit on/off toggle
- **Keyboard**: Enter/Space toggles, arrow keys navigate between pills

Component breakdown:
- `RxDspPillRow.svelte` -- container, renders pills, manages popover state
- `DspPill.svelte` -- individual pill (generic: label, active state, color, click handler)
- `DspPopover.svelte` -- generic popover container (positioned below pill, closes on outside click/Escape)
- `HighpassConfig.svelte` -- frequency slider 100-300 Hz
- `LowpassConfig.svelte` -- frequency slider 2500-3500 Hz
- `BandpassConfig.svelte` -- preset selector + custom range controls
- `NotchConfig.svelte` -- center/width sliders + auto-notch toggle (future)
- `PeakFilterConfig.svelte` -- frequency + Q sliders
- `NoiseBlankerConfig.svelte` -- threshold slider
- `NrConfig.svelte` -- amount slider
- `CompressorConfig.svelte` -- threshold/ratio sliders
- `EqConfig.svelte` -- bass/mid/treble sliders

The existing `DspPanel.svelte` (accordion-style) is replaced by this pill row for the RX chain. The old component can be removed or kept as an alternative layout option.

#### TX DSP Controls -- PTT Box Configuration Menu

The TX DSP controls are accessed via a configuration button (gear icon) near the PTT button. Clicking it opens a modal or slide-out panel with all TX chain settings. This is a less-frequently-accessed configuration surface -- operators set it once and rarely change it during operation.

Component breakdown:
- `TxDspMenu.svelte` -- modal/slide-out panel containing all TX DSP controls
- `TxFilterSection.svelte` -- highpass + lowpass controls
- `TxEqSection.svelte` -- 3-band EQ
- `TxCompressorSection.svelte` -- preset selector + manual controls (threshold, ratio, attack, release)
- `TxLimiterSection.svelte` -- threshold display (auto-managed with compressor)
- `TxNoiseGateSection.svelte` -- threshold slider + link to VOX threshold

#### State Management

DSP state is managed by the chain classes themselves (`RxDspChain` and `TxDspChain`). The Svelte components read from and write to these classes. On any parameter change:

1. The chain class updates the Web Audio node immediately (real-time audio change)
2. A Svelte `$effect` debounces and calls `POST /api/radio/{id}/dsp` to persist

On page load:
1. `AudioManager.startRx()` / `startTx()` build the chains with default parameters
2. `GET /api/radio/{id}/dsp` fetches persisted settings
3. Settings are applied to the chain classes, which update their Web Audio nodes

### Trade-offs and Decisions

| Decision | Rationale |
|----------|-----------|
| Separate RX and TX chain classes | They have different nodes, different defaults, and different UI surfaces. A single class would be overloaded with conditional logic. |
| Noise blanker as AudioWorklet, not BiquadFilter | Noise blanking requires time-domain impulse detection and sample replacement, which is not expressible as a frequency-domain filter. An AudioWorklet gives sample-level control. |
| Bandpass presets as coordinated filter settings | Rather than adding a new node type, presets configure the existing highpass + lowpass + bandpass nodes in concert. Simpler, fewer nodes in the graph. |
| Limiter as a separate DynamicsCompressorNode | A limiter is just a compressor with extreme ratio (20:1) and fast attack. Using a dedicated node keeps the compressor and limiter independently tunable. |
| Persist DSP to backend config, not localStorage | Backend config is the single source of truth for all per-radio settings. Keeps DSP settings alongside radio config, survives browser/device changes, and is included in config export/import. |
| TX chain inserted before PCM worklet, not after | Processing before encoding means the PCM sent over WebSocket is already processed. The operator hears what the radio will transmit. The backend does not need to know about DSP. |
| Pills for RX, menu for TX | RX DSP is adjusted during operation (reacting to band conditions). TX DSP is configured once per session. Different interaction frequencies demand different UI patterns. |
| RX pills below frequency display, not in separate panel | Keeps the most-used DSP controls in the operator's primary visual field without requiring panel navigation. |

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
| TX DSP chain adds latency to mic path | Low | Web Audio nodes process in 128-sample quanta (~8ms at 16 kHz). Even with 8 nodes in series, total added latency is under 15ms -- imperceptible for voice. |
| Noise blanker AudioWorklet browser compatibility | Low | AudioWorklet is supported in all modern browsers (Chrome 66+, Firefox 76+, Safari 14.1+). The existing NR worklet already validates this path. |
| DSP config save storms during rapid adjustment | Medium | Client-side debounce (500ms) coalesces rapid parameter changes into a single save. The UI remains responsive because audio changes are instant (Web Audio node updates) while persistence is async. |
| Popover positioning on small screens | Medium | Use a utility like Floating UI (Popper successor) or manual viewport-aware positioning. Fall back to a bottom sheet on narrow screens. |
| Per-radio DSP config bloats config.yaml | Low | DSP config adds ~40 lines per radio. For 1-3 radios this is negligible. The YAML remains human-readable. |
| Unauthorized transmitter keying over LAN | High | Session-cookie password auth with bcrypt hashing and itsdangerous-signed HttpOnly cookies. See Security Model section. |
| rigctld command injection via mode strings | High | Validate all user-supplied strings (mode, VFO) against known allowlists before interpolating into rigctld protocol commands. |
| Concurrent config mutation (lost updates) | Medium | Config read-modify-write cycles across multiple endpoints have no locking. Add an `asyncio.Lock` around config mutation paths. |
| Single SSE subscriber starves others | Medium | The device event queue is single-consumer. Multiple SSE clients (e.g., two browser tabs on the setup wizard) cause event loss. Replace with a broadcast pattern (one queue per subscriber). |
| Float precision in frequency conversion | Low | `int(mhz * 1_000_000)` truncates rather than rounds, causing off-by-one Hz errors (e.g., 14.074 MHz becomes 14073999 Hz). Use `round()` before `int()`. |
| Waterfall subprocess leak on connection displacement | Medium | When a new waterfall WebSocket displaces the previous one, the old `pw-record` subprocess is not terminated. It runs orphaned until it fails on its own. |
| DSP changes dropped on page navigation | Medium | `DspPersistence.destroy()` clears pending debounced saves instead of flushing them. Operators who adjust a knob and immediately navigate lose changes. |

---

## Architecture Decisions

| # | Topic | Decision |
|---|-------|----------|
| 1 | Frontend framework | **Svelte** -- lightweight, no virtual DOM, well-suited for real-time canvas/WebSocket work |
| 2 | FFT computation | **Subprocess-based PipeWire capture** -- each radio spawns a `pw-record` subprocess; the waterfall router reads its stdout asynchronously and computes FFT server-side. This is a pragmatic simplification from the originally planned dedicated-thread model, trading architectural purity for implementation simplicity. |
| 3 | rigctld polling interval | **100ms default**, configurable via `polling_interval_ms` in `config.yaml`; do not poll below ~50ms to avoid overwhelming radio CAT buffers |
| 4 | Static file serving | **FastAPI StaticFiles** to start (one-line, zero extra deps); Caddy can be added later as a layer in the rpi-image build to enable HTTPS/HTTP2 without code changes |
| 5 | Config conflict error format | **RFC 7807 Problem Details** with `409 Conflict`; `errors` array identifies each conflict by type, field path, conflicting radio ID, and value |
| 6 | Client-side DSP | **Web Audio API** -- BiquadFilterNode for filters/EQ, DynamicsCompressorNode for compression, custom AudioWorklets for noise reduction and squelch. Runs entirely in browser, no Pi CPU cost. |
| 7 | Visualization architecture | **Pluggable renderers** -- all visualization modes receive the same data (FFT bins + raw PCM). A renderer interface allows adding new visualizations without changing the data pipeline. |
| 8 | Layout system | **JSON-serializable layout configs** -- each layout is a JSON document describing which components are visible and their arrangement. Stored in browser localStorage and optionally exported as files. |
| 9 | Input abstraction | **Event-driven control model** -- controls respond to abstract "change" events, not specific input devices. This allows keyboard, mouse scroll, touch, and future hardware controllers to drive the same controls. |
| 10 | DSP chain separation | **Independent RX and TX chains** -- separate class, separate node graph, separate UI surface. RX chain extends the existing `DspChain`; TX chain is a new `TxDspChain` class. Both are per-radio, instantiated by `AudioManager`. |
| 11 | DSP persistence | **Backend config, not localStorage** -- DSP settings are stored in the YAML config under each radio's `dsp` section. Frontend debounces saves. This keeps all per-radio state in one place and survives browser/device changes. |
| 12 | RX DSP UI pattern | **Pill row below frequency display** -- compact, always-visible toggles for the most frequently adjusted DSP features. Click toggles, click-when-active opens configuration popover. Replaces the accordion-style DspPanel. |
| 13 | TX DSP UI pattern | **Configuration menu near PTT** -- a gear button opens a modal/slide-out with all TX chain settings. Less frequently adjusted than RX, so it can afford a heavier interaction pattern. |

### Config Validation

Config is modelled as **Pydantic models** -- FastAPI already depends on Pydantic, so this is a zero-cost dependency. Benefits:
- Field-level type coercion and validation on both file load and `POST /api/config`
- Cross-radio uniqueness checks (duplicate serial ports, duplicate audio devices) via `@model_validator`
- Single source of truth: same models validate the YAML on disk and the API request body
- Pydantic `ValidationError` structure maps directly onto the RFC 7807 `errors` array format

**Validation gap**: The `RadioConfig.id` field currently accepts any string. It needs a `field_validator` constraining it to safe characters (e.g., `^[a-z0-9_-]+$`) because the ID is used in filesystem paths and systemd unit names. Similarly, `serial_port` and other string fields written to env files need format validation to prevent newline injection.

---

## Known Limitations and Technical Debt

Issues identified by audit (2026-03-29) that are understood and tracked for resolution.

### Correctness

- **S-meter over-S9 loss**: The S-meter conversion formula (`state.py`) clamps values to S0-S9, discarding all "over S9" information. Readings above S9 (e.g., S9+20dB) are reported as plain S9. The UI needs the raw dBm value to display above-S9 readings correctly.

- **Float-to-Hz truncation**: `int(mhz * 1_000_000)` truncates instead of rounding, causing off-by-one Hz errors on certain frequencies (e.g., 14.074 MHz becomes 14073999 Hz due to IEEE 754 representation). Fix: `round(mhz * 1_000_000)`.

- **Control WS state ordering**: The poll loop and the immediate-echo after set commands can race, potentially delivering out-of-order state updates if a poll runs between a set command and its echo response.

### Resource Management

- **Waterfall subprocess leak**: When a new waterfall WebSocket connection displaces the previous one, the old `pw-record` subprocess continues running orphaned. Unlike the control and audio WebSocket handlers (which explicitly close the previous connection), the waterfall handler simply overwrites `radio.ws_waterfall` without terminating the old capture process.

- **Single-consumer SSE queue**: The device event SSE stream uses a single `asyncio.Queue`. Multiple subscribers (e.g., two browser tabs on the setup wizard) steal events from each other. The setup wizard's SSE handler is also a no-op that dequeues events without processing them, further exacerbating the problem.

- **Config mutation race condition**: Multiple endpoints (`POST /config`, `PATCH /radios/{id}/dsp`, `POST /presets`, etc.) perform read-modify-write on `app.state.config` without any locking. Concurrent requests can cause lost updates. An `asyncio.Lock` is needed around config mutation paths.

- **DSP persistence drops changes on navigation**: `DspPersistence.destroy()` clears pending debounced saves rather than flushing them. Adjusting a DSP knob and immediately navigating away silently loses the change.

### Code Quality

- **`itsdangerous` and `bcrypt` dependencies**: Used by the authentication system for session cookie signing and password hashing respectively. See Security Model section.

- **Duplicate `RadioDep` type alias**: Defined in both `deps.py` (canonical) and `audio.py` (local copy). The local copy could silently diverge.

- **RX DSP config application duplication**: The code that applies RX DSP settings from config to the chain is copy-pasted between the simulation branch and the real-radio branch in `+page.svelte`.

- **Dead code**: `_MONITOR_START` in `devices.py` is computed at import time but never referenced. The `rx-float` message handler in the audio worklet message handler is never triggered.

- **`image/` vs `deployment/` directory**: CLAUDE.md references `image/` but the actual directory is `deployment/`. Documentation should be updated to match.
