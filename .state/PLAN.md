# Riglet -- Implementation Plan

> Generated from `.state/OVERVIEW.md` and `riglet-handoff.md`.
> v1 scope: single radio (IC-7300), setup wizard, main UI with waterfall/audio/CAT control.

---

## Phase 1 -- Project Scaffolding

All tasks in this phase are sequential.

### 1.1 [x] Create `server/pyproject.toml` with dependencies and tool config
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/server/pyproject.toml`
- **Details**:
  - `[project]` section: name=riglet, python requires >=3.11
  - Runtime deps: `fastapi`, `uvicorn[standard]`, `pydantic>=2`, `pyyaml`, `numpy`, `pyserial`, `sse-starlette`, `itsdangerous`
  - Dev deps group: `ruff`, `mypy`, `pytest`, `pytest-asyncio`, `httpx` (for TestClient)
  - `[tool.ruff]` section: target-version="py311", line-length=99, select=["E","F","I","UP","B","SIM"]
  - `[tool.mypy]` section: strict=true, plugins=["pydantic.mypy"]
  - Build system: hatchling
- **Done when**: `cd /Users/wells/Projects/riglet/server && uv sync` succeeds and creates `.venv`

### 1.2 [x] Create directory structure and placeholder files
- **Agent**: @developer
- **Files to create** (empty `__init__.py` where noted):
  - `server/__init__.py` (empty)
  - `server/main.py` (empty, will be populated in Phase 3)
  - `server/state.py` (empty)
  - `server/config.py` (empty)
  - `server/devices.py` (empty)
  - `server/routers/__init__.py` (empty)
  - `server/routers/system.py` (empty)
  - `server/routers/devices.py` (empty)
  - `server/routers/cat.py` (empty)
  - `server/routers/audio.py` (empty)
  - `server/routers/waterfall.py` (empty)
  - `image/` directory (empty for now)
  - `ui/` directory (Svelte app root, created in Phase 8)
- **Done when**: All directories exist, `ruff check server/` passes (no errors on empty files)

### 1.3 [x] Create `.gitignore` additions
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/.gitignore`
- **Add entries for**: `__pycache__/`, `*.pyc`, `.venv/`, `server/.venv/`, `node_modules/`, `ui/build/`, `ui/dist/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `*.egg-info/`
- **Done when**: File updated, no untracked noise from tool caches

---

## Phase 2 -- Config Schema

Tasks 2.1 and 2.2 are sequential (2.2 depends on 2.1).

### 2.1 [x] Implement Pydantic config models in `server/config.py`
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/server/config.py`
- **Models to define**:
  - `OperatorConfig(BaseModel)`: `callsign: str`, `grid: str = ""`
  - `NetworkConfig(BaseModel)`: `hostname: str = "riglet"`, `http_port: int = 8080`
  - `AudioGlobalConfig(BaseModel)`: `sample_rate: int = 16000`, `chunk_ms: int = 20`
  - `RadioConfig(BaseModel)`: `id: str`, `name: str`, `hamlib_model: int`, `serial_port: str`, `baud_rate: int = 19200`, `ptt_method: Literal["cat","vox","rts","dtr"] = "cat"`, `audio_source: str = ""`, `audio_sink: str = ""`, `rigctld_port: int = 4532`, `enabled: bool = False`, `polling_interval_ms: int = 100`
    - Field validator: `polling_interval_ms` must be >= 50
    - Field validator: if `enabled` is True, `audio_source` and `audio_sink` must be non-empty
  - `RigletConfig(BaseModel)`: `operator: OperatorConfig`, `network: NetworkConfig`, `audio: AudioGlobalConfig`, `radios: list[RadioConfig] = []`
    - `@model_validator(mode="after")`: serial_port uniqueness across enabled radios
    - `@model_validator(mode="after")`: audio_source uniqueness across enabled radios
    - `@model_validator(mode="after")`: audio_sink uniqueness across enabled radios
    - `@model_validator(mode="after")`: rigctld_port uniqueness across all radios
    - `@model_validator(mode="after")`: radio id uniqueness
- **Functions to define**:
  - `load_config(path: Path = Path("/etc/riglet/config.yaml")) -> RigletConfig` -- reads YAML, returns validated model. Raises `FileNotFoundError` or `pydantic.ValidationError`.
  - `save_config(config: RigletConfig, path: Path = Path("/etc/riglet/config.yaml")) -> None` -- serializes to YAML, writes atomically (write to tmp + rename).
  - `default_config() -> RigletConfig` -- returns a config with no radios (triggers setup wizard).
- **Done when**: `pytest server/tests/test_config.py` passes (see 2.2)

### 2.2 [x] Write unit tests for config validation
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/server/tests/test_config.py`
- **Test cases**:
  - Valid config with two enabled radios loads successfully
  - Duplicate serial_port across enabled radios raises ValidationError
  - Duplicate audio_source across enabled radios raises ValidationError
  - Duplicate rigctld_port raises ValidationError
  - Duplicate radio id raises ValidationError
  - Disabled radio with empty audio fields passes validation
  - Enabled radio with empty audio_source fails validation
  - polling_interval_ms < 50 fails validation
  - `load_config` round-trips through `save_config` (write then read, compare)
  - `default_config()` returns config with empty radios list
- **Done when**: All tests pass, `ruff check` and `mypy server/config.py` clean

---

## Phase 3 -- Backend Core

Tasks 3.1 through 3.4 are sequential.

### 3.1 [x] Implement `RadioInstance` and `RadioManager` in `server/state.py`
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/server/state.py`
- **Classes**:
  - `RadioInstance`:
    - Fields: `id: str`, `config: RadioConfig`, `freq: float = 0.0`, `mode: str = "USB"`, `ptt: bool = False`, `online: bool = False`, `rx_volume: int = 50`, `tx_gain: int = 50`, `nr_level: int = 0`, `simulation: bool = False`
    - `rigctld_reader: asyncio.StreamReader | None`, `rigctld_writer: asyncio.StreamWriter | None`
    - `ws_control: WebSocket | None`, `ws_audio: WebSocket | None`, `ws_waterfall: WebSocket | None`
    - `_poll_task: asyncio.Task | None`
    - Method: `async connect_rigctld() -> bool` -- opens TCP to `localhost:{config.rigctld_port}`. On failure, sets `simulation=True`, `online=False`, returns False.
    - Method: `async send_command(cmd: str) -> str` -- writes Hamlib extended protocol command, reads response. Raises on timeout (2s).
    - Method: `async get_freq() -> float` -- sends `+\get_freq\n`, parses MHz float.
    - Method: `async get_mode() -> str` -- sends `+\get_mode\n`, parses mode string.
    - Method: `async set_freq(mhz: float) -> None`
    - Method: `async set_mode(mode: str) -> None`
    - Method: `async set_ptt(active: bool) -> None`
    - Method: `async get_smeter() -> tuple[int, int]` -- returns (S-units, dBm).
    - Method: `async poll_once() -> dict` -- calls get_freq, get_mode, get_smeter; returns dict of changed fields (compared to current state). Updates internal state.
    - Method: `async start_polling() -> None` -- starts asyncio task that calls `poll_once()` every `config.polling_interval_ms` ms and pushes changes to `ws_control`.
    - Method: `async stop_polling() -> None`
    - Method: `async disconnect() -> None` -- stops polling, closes rigctld connection, closes all WS.
  - `RadioManager`:
    - `radios: dict[str, RadioInstance]`
    - `config: RigletConfig`
    - Method: `async startup(config: RigletConfig) -> None` -- creates RadioInstance per enabled radio, calls `connect_rigctld()`, starts polling.
    - Method: `async shutdown() -> None` -- disconnects all radios.
    - Method: `get(radio_id: str) -> RadioInstance` -- raises `KeyError` if not found.
    - Method: `def status() -> list[dict]` -- returns list of `{id, name, online, freq, mode, ptt}` per radio.
- **Done when**: `mypy server/state.py` passes. Unit test for simulation mode (no rigctld) passes.

### 3.2 [x] Implement FastAPI app shell in `server/main.py`
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/server/main.py`
- **Details**:
  - Create `FastAPI` app instance with title="Riglet", version="0.1.0"
  - Lifespan context manager:
    - On startup: `load_config()` (fallback to `default_config()` if file missing), instantiate `RadioManager`, call `manager.startup(config)`, store manager in `app.state.manager` and config in `app.state.config`
    - On shutdown: `manager.shutdown()`
  - Mount static files: `app.mount("/", StaticFiles(directory="/opt/riglet/app/static", html=True), name="static")` -- but only if that directory exists, otherwise skip (dev mode)
  - Include all routers from `server/routers/` with prefix `/api`
  - Add dependency function `get_manager(request: Request) -> RadioManager` that reads from `request.app.state.manager`
  - Add dependency function `get_radio(radio_id: str, manager: RadioManager = Depends(get_manager)) -> RadioInstance` that calls `manager.get(radio_id)` and raises `HTTPException(404)` on KeyError
  - Add RFC 7807 exception handler for `pydantic.ValidationError` returning 409 with `{"type": "validation_error", "title": "Config Validation Failed", "errors": [...]}`
  - Entry point: `if __name__ == "__main__": uvicorn.run("server.main:app", host="0.0.0.0", port=config.network.http_port, reload=False)`
- **Done when**: `uvicorn server.main:app` starts without error (no radios configured, no static dir, returns 404 on `/`)

### 3.3 [x] Write tests for RadioInstance simulation mode
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/server/tests/test_state.py`
- **Test cases**:
  - `RadioInstance.connect_rigctld()` with no server listening sets `simulation=True`
  - In simulation mode, `get_freq()` returns a default value (e.g., 14.074)
  - In simulation mode, `set_freq()` updates internal state without error
  - `poll_once()` in simulation mode returns synthetic state
  - `RadioManager.startup()` with empty radios list succeeds
  - `RadioManager.get("nonexistent")` raises KeyError
- **Done when**: All tests pass

### 3.4 [x] Implement rigctld Hamlib protocol details
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/server/state.py` (extend)
- **Details**:
  - Ensure `send_command` uses Hamlib extended protocol: prefix commands with `+`, parse `RPRT` response codes
  - Handle `RPRT -x` error codes: map to meaningful exceptions (e.g., `RigctldError(code, message)`)
  - Implement timeout handling: if read takes >2s, mark radio as offline, log warning, attempt reconnect on next poll
  - Implement reconnect logic: if `online=False`, try reconnecting every 5 seconds during poll loop
- **Done when**: `mypy` clean, existing tests still pass

---

## Phase 4 -- REST API Routes

Tasks 4.1 through 4.5 can run in parallel (they are independent routers).

### 4.1 [x] Implement system routes in `server/routers/system.py`
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/server/routers/system.py`
- **Endpoints**:
  - `GET /api/status` -- returns `{"status": "ok", "radios": [manager.status()]}`. If no radios enabled, include `"setup_required": true`.
  - `GET /api/config` -- returns current `RigletConfig` as JSON (via Pydantic `.model_dump()`)
  - `POST /api/config` -- accepts `RigletConfig` JSON body, validates (Pydantic does this automatically), calls `save_config()`. On ValidationError, return 409 RFC 7807. On success, return 200 with saved config.
  - `POST /api/config/restart` -- check no radio has PTT active (409 if any). Send `service_restart` event to all WS clients. Write `.env` files from config. Call `systemctl restart` via `asyncio.create_subprocess_exec`. Return 200.
  - `GET /api/logs/{service}` -- run `journalctl -u {service} -n 100 --no-pager` via subprocess, return lines as JSON array. Validate service name against allowlist: `["riglet", "rigctld@radio1", "rigctld@radio2", ...]`.
  - `GET /api/hamlib/models` -- run `rigctl -l` via subprocess, parse output into `[{"id": int, "name": str}]`. Cache result (models do not change at runtime).
- **Helper function**: `write_env_files(config: RigletConfig) -> None` -- for each enabled radio, write `/etc/riglet/radio-{id}.env` with `HAMLIB_MODEL`, `SERIAL_PORT`, `BAUD_RATE`, `RIGCTLD_PORT`, `PTT_METHOD`.
- **Done when**: Tests for GET /api/status and POST /api/config pass

### 4.2 [x] Implement device discovery routes in `server/routers/devices.py`
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/server/routers/devices.py`
- **Depends on**: `server/devices.py` (created in 4.2a)
- **Endpoints**:
  - `GET /api/devices/serial` -- calls `discover_serial_devices()`, returns `[{"port": str, "vid": str, "pid": str, "description": str, "guessed_model": int | null}]`
  - `GET /api/devices/audio` -- calls `discover_audio_devices()`, returns `[{"id": str, "name": str, "source": str, "sink": str, "vid": str, "pid": str}]`
  - `GET /api/devices/events` -- SSE endpoint using `sse-starlette`. Subscribes to a shared `asyncio.Queue` that is fed by the udev monitor.
- **Done when**: Serial and audio endpoints return data (mocked in tests)

### 4.2a [x] Implement device discovery logic in `server/devices.py`
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/server/devices.py`
- **Functions**:
  - `discover_serial_devices() -> list[SerialDevice]` -- uses `serial.tools.list_ports.comports()`. For each port, extract VID/PID. Guess Hamlib model by matching known VID/PID pairs (IC-7300 = 10c4:ea60, etc). Return list of `SerialDevice` dataclass.
  - `discover_audio_devices() -> list[AudioDevice]` -- run `pw-cli list-objects Node` or parse `pactl list sources/sinks short`, group source+sink by USB device path. Return list of `AudioDevice` dataclass.
  - `class UdevMonitor` -- async context manager that starts a background thread watching `/dev` for USB serial and audio device add/remove events. Pushes `DeviceEvent(action: "added"|"removed", device_type: "serial"|"audio", details: dict)` to an `asyncio.Queue`.
  - VID/PID lookup table: `KNOWN_RADIOS = {("10c4","ea60"): "Silicon Labs CP210x (IC-7300, ...)", ...}`
- **Done when**: `discover_serial_devices()` works on dev machine (returns empty list if no USB serial). `mypy` clean.

### 4.3 [x] Implement CAT control routes in `server/routers/cat.py`
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/server/routers/cat.py`
- **Endpoints** (all scoped to `{radio_id}`):
  - `GET /api/radio/{radio_id}/cat` -- returns `{"freq": float, "mode": str, "ptt": bool, "online": bool}`
  - `POST /api/radio/{radio_id}/cat/freq` -- body `{"freq": float}`, calls `radio.set_freq()`, returns updated state
  - `POST /api/radio/{radio_id}/cat/mode` -- body `{"mode": str}`, calls `radio.set_mode()`
  - `POST /api/radio/{radio_id}/cat/ptt` -- body `{"active": bool}`, calls `radio.set_ptt()`
  - `POST /api/radio/{radio_id}/cat/nudge` -- body `{"direction": int}` (+1 or -1), computes `radio.freq + direction * 0.001`, calls `set_freq()`
  - `POST /api/radio/{radio_id}/cat/test` -- attempts `radio.get_freq()`, returns `{"success": true, "freq": float}` or `{"success": false, "error": str}`
- **Pydantic request models**: `FreqRequest`, `ModeRequest`, `PttRequest`, `NudgeRequest`
- **Done when**: Tests with simulation-mode radio pass

### 4.4 [x] Implement audio control routes in `server/routers/audio.py`
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/server/routers/audio.py`
- **REST Endpoints**:
  - `GET /api/radio/{radio_id}/audio` -- returns `{"rx_volume": int, "tx_gain": int, "nr_level": int, "sample_rate": 16000, "chunk_ms": 20}`
  - `POST /api/radio/{radio_id}/audio/volume` -- body `{"rx_volume": int, "tx_gain": int, "nr_level": int}`, validates ranges (0-100, 0-100, 0-10), updates RadioInstance
  - `POST /api/radio/{radio_id}/audio/test` -- generates 1kHz sine wave (1 second, s16le, 16kHz), writes to PipeWire sink via `pw-play` subprocess or direct PipeWire client. Returns 200 on success.
- **WebSocket endpoint** (placeholder -- full implementation in Phase 5):
  - `WS /api/radio/{radio_id}/ws/audio` -- accept connection, store in `radio.ws_audio`. Binary bidirectional.
- **Done when**: REST endpoints tested, WS accepts connection

### 4.5 [x] Implement waterfall WebSocket route in `server/routers/waterfall.py`
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/server/routers/waterfall.py`
- **WebSocket endpoint** (placeholder -- full FFT in Phase 5):
  - `WS /api/radio/{radio_id}/ws/waterfall` -- accept connection, store in `radio.ws_waterfall`. Server-to-client only.
  - In simulation mode: send synthetic FFT frames (random noise) at 10 fps for UI development.
- **Done when**: Simulation waterfall sends JSON frames to connected WS client

---

## Phase 5 -- WebSocket Channels and Audio Pipeline

Tasks 5.1 and 5.2 are sequential. Task 5.3 depends on both.

### 5.1 [~] Implement Control WebSocket in `server/routers/cat.py`
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/server/routers/cat.py` (extend)
- **Endpoint**: `WS /api/radio/{radio_id}/ws/control`
- **Details**:
  - On connect: store in `radio.ws_control`. Send initial state snapshot (`freq`, `mode`, `ptt`, `smeter`, `radio_status`).
  - Receive loop: parse JSON messages. Dispatch by `type` field:
    - `"freq"` -> `radio.set_freq(msg["freq"])`
    - `"mode"` -> `radio.set_mode(msg["mode"])`
    - `"ptt"` -> `radio.set_ptt(msg["active"])`
    - `"nudge"` -> compute new freq, `radio.set_freq(new_freq)`
  - On error: send `{"type": "error", "code": "...", "message": "..."}` over WS
  - On disconnect: clear `radio.ws_control`
  - Polling integration: `RadioInstance.poll_once()` should push changed fields to `ws_control` via `ws.send_json()`
- **Done when**: Connect to WS, receive initial state, send freq command, see updated freq pushed back

### 5.2 [~] Implement audio capture/playback pipeline in `server/routers/audio.py`
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/server/routers/audio.py` (extend)
- **Details**:
  - **RX path**: Start a dedicated thread per radio (via `asyncio.to_thread` or `threading.Thread`) that opens PipeWire capture stream for `radio.config.audio_source`. Read 20ms chunks (640 bytes at 16kHz s16le mono). Put chunks into `asyncio.Queue(maxsize=50)`. WS handler drains queue, sends binary frames.
  - **TX path**: WS handler receives binary frames from client. If `radio.ptt` is True, write to PipeWire playback stream for `radio.config.audio_sink`. If PTT is False, silently drop.
  - **PipeWire interaction**: Use subprocess `pw-record` / `pw-play` for initial implementation. Target device by PipeWire node name from config.
  - **Volume control**: Apply `rx_volume` scaling to RX audio before sending (numpy multiply + clip). Apply `tx_gain` to TX audio before playback.
  - **Simulation mode**: If audio device not available, generate silence (RX) and discard (TX). Log warning once.
- **Done when**: With a real or simulated audio device, RX audio streams to WS client, TX audio from WS is played (when PTT active)

### 5.3 [~] Implement server-side FFT for waterfall in `server/routers/waterfall.py`
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/server/routers/waterfall.py` (extend)
- **Details**:
  - Start a dedicated daemon thread per radio that captures audio from PipeWire at 48kHz (separate stream from the 16kHz audio WS stream, or resample).
  - Accumulate samples into 512-sample windows (for 256 bins via `numpy.fft.rfft`).
  - Compute magnitude spectrum, convert to log scale, normalize to 0.0-1.0 range.
  - Push FFT frame dict `{"type": "fft", "bins": [...], "center_mhz": float, "span_khz": 48.0}` into `asyncio.Queue(maxsize=20)`.
  - WS handler drains queue at ~10 fps, sends JSON.
  - `center_mhz` comes from `radio.freq` (current VFO frequency).
- **Done when**: Waterfall WS sends real FFT data from audio capture (or synthetic in simulation mode). 10 fps verified.

---

## Phase 6 -- Svelte SPA

Tasks 6.1 through 6.5 are sequential (each builds on the previous).

### 6.1 [ ] Scaffold Svelte project in `ui/`
- **Agent**: @developer
- **Directory**: `/Users/wells/Projects/riglet/ui/`
- **Details**:
  - Initialize with `npx sv create` (Svelte 5, SvelteKit in SPA/static mode)
  - Configure `svelte.config.js` for static adapter (output to `../server/static/` or a build target)
  - Add Vite config for dev proxy: proxy `/api` and `/api/radio/*/ws/*` to `localhost:8080`
  - Install dependencies: `@sveltejs/adapter-static`
  - Verify `npm run dev` starts and shows default page
  - Verify `npm run build` produces static files
- **Done when**: `npm run dev` shows Svelte welcome page, `npm run build` outputs to static dir

### 6.2 [ ] Build shared services and stores
- **Agent**: @developer
- **Files**:
  - `ui/src/lib/api.ts` -- REST API client functions: `getStatus()`, `getConfig()`, `postConfig()`, `getSerialDevices()`, `getAudioDevices()`, `getRadioCat()`, `postFreq()`, `postMode()`, `postPtt()`, `postNudge()`, `postCatTest()`, `postAudioVolume()`, `postAudioTest()`, `getHamlibModels()`, `postConfigRestart()`
  - `ui/src/lib/stores.ts` -- Svelte stores: `radioState` (freq, mode, ptt, smeter, online), `config` (RigletConfig), `setupStep` (wizard step index), `claimedResources` (resource exclusivity map)
  - `ui/src/lib/websocket.ts` -- WebSocket manager class: connects to control/audio/waterfall WS per radio. Auto-reconnect with backoff. Dispatches messages to stores.
  - `ui/src/lib/audio-worklet.ts` -- AudioWorklet processor for PCM ring buffer (RX playback + TX capture). Handles s16le <-> Float32 conversion.
  - `ui/src/lib/types.ts` -- TypeScript interfaces matching backend Pydantic models
- **Done when**: API client functions compile, stores are reactive, WS manager connects in dev mode

### 6.3 [ ] Implement setup wizard UI
- **Agent**: @developer
- **Files**:
  - `ui/src/routes/setup/+page.svelte` -- Wizard container with step navigation (5 steps)
  - `ui/src/lib/components/wizard/Welcome.svelte` -- Step 1: hostname input, optional password
  - `ui/src/lib/components/wizard/DetectRadios.svelte` -- Step 2: serial device cards, model dropdown, baud rate, "Test CAT" button
  - `ui/src/lib/components/wizard/MapAudio.svelte` -- Step 3: audio interface dropdown per radio, "Test audio" button, claimed-resource greying
  - `ui/src/lib/components/wizard/PttMethod.svelte` -- Step 4: PTT method radio buttons per radio
  - `ui/src/lib/components/wizard/ReviewApply.svelte` -- Step 5: config summary, "Apply and start" button, validation error display
- **Behavior**:
  - Steps are sequential with Back/Next navigation
  - Each step is skippable (Next always enabled)
  - Resource exclusivity: `claimedResources` store updated on audio assignment; greyed items show "In use by {radio}"
  - SSE subscription for hotplug events during wizard (device_added/removed updates device lists)
  - On "Apply and start": POST config, on success POST restart, enter reconnect loop (poll /api/status every 1s, 30s timeout), redirect to main UI
- **Done when**: Wizard renders all 5 steps, form inputs work, API calls fire correctly

### 6.4 [ ] Implement main radio UI
- **Agent**: @developer
- **Files**:
  - `ui/src/routes/+page.svelte` -- Main UI page. If `setup_required` from /api/status, redirect to /setup.
  - `ui/src/lib/components/Waterfall.svelte` -- Canvas element. Receives FFT frames from waterfall WS. Scrolling waterfall display with color gradient (blue->yellow->red). 256 bins wide, scrolls vertically.
  - `ui/src/lib/components/FrequencyDisplay.svelte` -- Large frequency readout in MHz. Click-to-edit (inline input). Band pill buttons (e.g., 20m, 40m, 80m) that jump to band edges. Nudge buttons (+/- 1kHz).
  - `ui/src/lib/components/ModeSelector.svelte` -- Mode buttons: USB, LSB, AM, FM, CW, RTTY, FT8. Active mode highlighted.
  - `ui/src/lib/components/PttButton.svelte` -- Large PTT button. Press-and-hold or toggle mode. Visual TX indicator (red background when active). Sends PTT commands via control WS for low latency.
  - `ui/src/lib/components/SmeterDisplay.svelte` -- S-meter bar/needle display. Updates from control WS smeter events.
  - `ui/src/lib/components/AudioControls.svelte` -- RX volume slider (0-100), TX gain slider (0-100). Mute button. Sends volume changes via REST.
- **Behavior**:
  - On mount: connect all 3 WebSockets (control, audio, waterfall)
  - Control WS updates radioState store -> reactive UI updates
  - Audio WS: RX audio -> AudioWorklet -> speakers. TX: mic -> AudioWorklet -> Audio WS (only when PTT active)
  - Waterfall canvas redraws on each FFT frame
  - Frequency/mode/nudge commands sent via control WS
- **Done when**: Full UI renders, waterfall scrolls (simulation data ok), frequency/mode controls update, PTT button toggles, audio plays

### 6.5 [ ] Implement AudioWorklet for browser audio
- **Agent**: @developer
- **Files**:
  - `ui/src/lib/audio/pcm-worklet-processor.js` -- AudioWorkletProcessor subclass
    - RX: receives s16le PCM via MessagePort, converts to Float32, writes to ring buffer, outputs to audio graph
    - TX: captures input from audio graph (mic), converts Float32 to s16le, sends via MessagePort
    - Ring buffer: 5 chunks deep (100ms at 20ms/chunk) to absorb jitter
  - `ui/src/lib/audio/audio-manager.ts` -- Creates AudioContext, registers worklet, connects mic input (getUserMedia), connects speaker output. Exposes `startRx()`, `stopRx()`, `startTx()`, `stopTx()`, `setVolume()`.
  - Integration with `websocket.ts`: audio WS binary frames are forwarded to/from the worklet via MessagePort.
- **Done when**: RX audio from server plays through browser speakers. TX audio from browser mic is captured and sent. No audio glitches at steady state.

---

## Phase 7 -- Systemd Units and Service Management

Tasks 7.1 and 7.2 can run in parallel. 7.3 depends on both.

### 7.1 [ ] Create systemd unit files
- **Agent**: @developer
- **Files**:
  - `image/files/riglet.service`:
    ```
    [Unit]
    Description=Riglet web application
    After=network.target avahi-daemon.service
    Wants=avahi-daemon.service

    [Service]
    Type=exec
    User=ham
    WorkingDirectory=/opt/riglet/app
    ExecStart=/opt/riglet/venv/bin/uvicorn server.main:app --host 0.0.0.0 --port 8080
    Restart=on-failure
    RestartSec=3
    Environment=RIGLET_CONFIG=/etc/riglet/config.yaml

    [Install]
    WantedBy=multi-user.target
    ```
  - `image/files/rigctld@.service`:
    ```
    [Unit]
    Description=Hamlib rigctld for %i
    After=network.target

    [Service]
    EnvironmentFile=/etc/riglet/radio-%i.env
    ExecStart=/usr/bin/rigctld -m ${HAMLIB_MODEL} -r ${SERIAL_PORT} -s ${BAUD_RATE} -t ${RIGCTLD_PORT}
    Restart=on-failure
    RestartSec=5
    User=ham

    [Install]
    WantedBy=multi-user.target
    ```
- **Done when**: Unit files are syntactically valid (`systemd-analyze verify` passes if available)

### 7.2 [ ] Implement env file generation and service control in backend
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/server/routers/system.py` (extend)
- **Details**:
  - `write_env_files(config: RigletConfig) -> None`:
    - For each enabled radio, write `/etc/riglet/radio-{id}.env` containing: `HAMLIB_MODEL={hamlib_model}`, `SERIAL_PORT={serial_port}`, `BAUD_RATE={baud_rate}`, `RIGCTLD_PORT={rigctld_port}`, `PTT_METHOD={ptt_method}`
    - Remove env files for disabled radios
  - `async restart_services(config: RigletConfig) -> None`:
    - `systemctl daemon-reload`
    - For each enabled radio: `systemctl enable --now rigctld@{id}`
    - For each disabled radio: `systemctl disable --now rigctld@{id}`
    - `systemctl restart riglet`
  - Guard all `systemctl` calls with try/except (graceful failure if not running on systemd, e.g., dev machine)
- **Done when**: `write_env_files` creates correct files. `restart_services` calls systemctl (or logs skip on non-systemd host).

### 7.3 [ ] Wire restart endpoint to service management
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/server/routers/system.py` (extend)
- **Details**:
  - `POST /api/config/restart` implementation:
    1. Check `manager.radios` -- if any radio has `ptt=True`, return 409 with RFC 7807 body
    2. For each radio with a `ws_control`, send `{"type": "service_restart", "reason": "config_change", "eta_seconds": 5}`
    3. Call `write_env_files(config)`
    4. Call `restart_services(config)` (this will restart the backend itself)
    5. Return 200 (client may not receive this if restart is fast)
- **Done when**: Endpoint works end-to-end in test (mocked systemctl)

---

## Phase 8 -- rpi-image-gen Image Build

All tasks in this phase are sequential.

### 8.1 [ ] Create rpi-image-gen profile
- **Agent**: @developer
- **Files**:
  - `image/config.ini` -- rpi-image-gen configuration for Pi 4, Bookworm 64-bit
  - `image/packages.txt`:
    ```
    python3
    python3-pip
    python3-venv
    git
    libhamlib4
    hamlib-utils
    pipewire
    pipewire-pulse
    wireplumber
    alsa-utils
    wsjtx
    libftdi1
    ser2net
    avahi-daemon
    udev
    curl
    ```
  - `image/files/config.yaml.default` -- default config with `operator: {callsign: "", grid: ""}`, `network: {hostname: riglet, http_port: 8080}`, `audio: {sample_rate: 16000, chunk_ms: 20}`, `radios: []`
- **Done when**: Files exist and are syntactically correct

### 8.2 [ ] Create post-install script
- **Agent**: @developer
- **File**: `image/scripts/01-configure.sh`
- **Actions** (idempotent):
  1. Create `ham` user, add to groups `dialout`, `audio`, `plugdev`
  2. `mkdir -p /opt/riglet/app /etc/riglet`
  3. Copy app files: `cp -r /path/to/server /opt/riglet/app/server`
  4. Copy static files: `cp -r /path/to/ui/build /opt/riglet/app/static` (if built)
  5. Create venv: `python3 -m venv /opt/riglet/venv`
  6. Install deps: `/opt/riglet/venv/bin/pip install -e /opt/riglet/app` (or `uv sync`)
  7. Copy systemd units: `cp riglet.service rigctld@.service /etc/systemd/system/`
  8. `systemctl daemon-reload && systemctl enable riglet avahi-daemon`
  9. Copy default config: `cp config.yaml.default /etc/riglet/config.yaml`
  10. Configure SSH: disable root login, enable password auth
  11. Set permissions: `chown -R ham:ham /opt/riglet /etc/riglet`
- **Done when**: Script is executable, passes `shellcheck`

---

## Phase 9 -- First-Boot Wizard Flow (End-to-End)

### 9.1 [ ] Implement setup-required detection and routing
- **Agent**: @developer
- **Files**: `server/main.py` (extend), `ui/src/routes/+page.svelte` (extend)
- **Details**:
  - Backend: `GET /api/status` includes `"setup_required": true` when `config.radios` is empty or no radio is enabled
  - Frontend: on app load, call `GET /api/status`. If `setup_required`, redirect to `/setup`. Otherwise show main UI.
  - After wizard completes and services restart, `/api/status` returns `setup_required: false`, frontend redirects to main UI.
- **Done when**: Fresh config -> wizard shown. After wizard completion -> main UI shown.

### 9.2 [ ] Implement reconnect loop in frontend
- **Agent**: @developer
- **File**: `ui/src/lib/reconnect.ts`
- **Details**:
  - Function `waitForRestart(timeoutMs: number = 30000): Promise<boolean>`
  - Polls `GET /api/status` every 1 second
  - On success (200 response with `status: "ok"`): resolve true
  - On timeout: resolve false, show diagnostic screen with link to `/api/logs/riglet`
  - Used by wizard Step 5 "Apply and start" and by control WS `service_restart` event handler
- **Done when**: After config restart, UI reconnects and transitions to main UI within 30s

---

## Phase 10 -- Integration Testing and v1 Acceptance

### 10.1 [ ] Write integration tests for API endpoints
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/server/tests/test_api.py`
- **Test cases** (using `httpx.AsyncClient` with FastAPI TestClient):
  - GET /api/status returns 200 with radio list
  - GET /api/config returns valid config JSON
  - POST /api/config with valid config returns 200
  - POST /api/config with duplicate serial_port returns 409
  - GET /api/devices/serial returns list (may be empty)
  - GET /api/devices/audio returns list (may be empty)
  - GET /api/radio/{id}/cat returns freq/mode/ptt (simulation mode)
  - POST /api/radio/{id}/cat/freq updates frequency
  - POST /api/radio/{id}/cat/ptt toggles PTT
  - POST /api/radio/{id}/cat/test returns success in simulation mode
  - GET /api/radio/{id}/audio returns volume config
  - POST /api/radio/{id}/audio/volume with valid values returns 200
  - POST /api/radio/{id}/audio/volume with out-of-range values returns 422
- **Done when**: All tests pass

### 10.2 [ ] Write WebSocket integration tests
- **Agent**: @developer
- **File**: `/Users/wells/Projects/riglet/server/tests/test_websockets.py`
- **Test cases**:
  - Control WS: connect, receive initial state, send freq command, receive updated freq
  - Control WS: send PTT active, verify state change pushed
  - Audio WS: connect, receive binary RX frames (simulation)
  - Waterfall WS: connect, receive JSON FFT frames at ~10 fps
  - Control WS: second connection to same radio replaces first (single operator)
- **Done when**: All tests pass

### 10.3 [ ] Verify v1 acceptance criteria checklist
- **Agent**: @tester
- **Checklist** (manual or scripted):
  - [ ] `uv sync` in `server/` succeeds
  - [ ] `ruff check server/` passes with zero errors
  - [ ] `mypy server/` passes with zero errors
  - [ ] `pytest server/tests/` all green
  - [ ] `npm run build` in `ui/` succeeds
  - [ ] Backend starts in simulation mode: `uvicorn server.main:app`
  - [ ] `GET /api/status` returns `setup_required: true` with no config
  - [ ] Setup wizard loads at `http://localhost:8080/setup`
  - [ ] Waterfall canvas renders (simulation data)
  - [ ] Frequency/mode controls update via control WS
  - [ ] PTT button toggles state
  - [ ] Audio worklet initializes without errors
  - [ ] Image build files (`image/`) are complete and syntactically valid
- **Done when**: All checklist items verified

---

## Parallelization Strategy

```
Phase 1 (sequential: 1.1 -> 1.2 -> 1.3)
  |
  v
Phase 2 (sequential: 2.1 -> 2.2)
  |
  v
Phase 3 (sequential: 3.1 -> 3.2 -> 3.3 -> 3.4)
  |
  v
Phase 4 (parallel wave):
  [4.1, 4.2, 4.2a, 4.3, 4.4, 4.5] -- all independent routers
  Note: 4.2 depends on 4.2a; all others are independent
  |
  v
Phase 5 (sequential: 5.1 -> 5.2 -> 5.3)
  |                                       Phase 7 (7.1 || 7.2 -> 7.3)
  v                                         |
Phase 6 (sequential: 6.1 -> 6.2 -> 6.3 -> 6.4 -> 6.5)
  |                                         |
  v                                         v
Phase 8 (sequential: 8.1 -> 8.2) -- can start after Phase 7
  |
  v
Phase 9 (sequential: 9.1 -> 9.2) -- depends on Phase 6 + Phase 7
  |
  v
Phase 10 (10.1 || 10.2, then 10.3) -- final validation
```

Notes:
- Phase 7 can run in parallel with Phases 5 and 6 (systemd units are independent of app code)
- Phase 8 can start as soon as Phase 7 is complete
- Phase 6 (Svelte) can start as soon as Phase 4 provides API endpoints to develop against
- Phase 10 requires all other phases to be complete
