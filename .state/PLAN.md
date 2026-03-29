# Riglet -- Implementation Plan

---

## Feature: v0.3.0 -- Per-Radio DSP Chains

**Status: COMPLETE** -- All 28 tasks finished.

<details>
<summary>Expand completed DSP plan (all tasks [x])</summary>

### Task Summary

| #  | Task                                                              | Priority | Agent      | Status | Depends On | Notes                                           |
|:---|:------------------------------------------------------------------|:---------|:-----------|:-------|:-----------|:------------------------------------------------|
| 01 | Config schema: add RxDspConfig and TxDspConfig Pydantic models    | P0       | @developer | [x]    | --         | Nested under RadioConfig                        |
| 02 | DSP config API: GET/PATCH per-radio DSP settings endpoint         | P0       | @developer | [x]    | 01         | `routers/dsp.py`, mount on `/api`               |
| 03 | RxDspChain: highpass filter node (100-300 Hz)                     | P1       | @developer | [x]    | --         | BiquadFilterNode highpass in `rx-dsp-chain.ts`  |
| 04 | RxDspChain: lowpass filter node (2.5-3.5 kHz)                    | P1       | @developer | [x]    | --         | BiquadFilterNode lowpass in `rx-dsp-chain.ts`   |
| 05 | RxDspChain: peak filter node                                     | P1       | @developer | [x]    | --         | BiquadFilterNode peaking in `rx-dsp-chain.ts`   |
| 06 | RxDspChain: noise blanker node (biquad notch at 50/60 Hz)        | P1       | @developer | [x]    | --         | BiquadFilterNode notch, switchable 50/60 Hz     |
| 07 | RxDspChain: notch filter node (auto/manual, BiquadFilterNode)    | P1       | @developer | [x]    | --         | Manual freq+Q or auto-detect                    |
| 08 | RxDspChain: bandpass filter (presets + manual range)              | P1       | @developer | [x]    | --         | Presets: 2.4 kHz voice, 500 Hz CW, manual       |
| 09 | RxDspChain: DSP noise reduction AudioWorklet                     | P1       | @developer | [x]    | --         | Spectral subtraction in `nr-worklet-processor.ts`|
| 10 | Wire RxDspChain into AudioManager RX playback path               | P0       | @developer | [x]    | 03-09      | Replace existing DspChain with RxDspChain       |
| 11 | TxDspChain: highpass + lowpass filter nodes                      | P1       | @developer | [x]    | --         | New class in `tx-dsp-chain.ts`                  |
| 12 | TxDspChain: 3-band EQ (3x BiquadFilterNode)                     | P1       | @developer | [x]    | 11         | lowshelf, peaking, highshelf                    |
| 13 | TxDspChain: vocal compressor (DynamicsCompressorNode)            | P1       | @developer | [x]    | 11         | Presets + manual params                         |
| 14 | TxDspChain: limiter stage (DynamicsCompressorNode, high ratio)   | P1       | @developer | [x]    | 11         | ratio >= 20, knee 0                             |
| 15 | TxDspChain: noise gate (threshold-based gate node)               | P1       | @developer | [x]    | 11         | GainNode snapped 0/1 by analyser RMS            |
| 16 | Wire TxDspChain into AudioManager TX capture path                | P0       | @developer | [x]    | 11-15      | Insert before PCM worklet                       |
| 17 | RxDspPillRow component                                           | P1       | @developer | [x]    | 10         | Pill row below freq display, active color       |
| 18 | RxDspPopover component                                           | P1       | @developer | [x]    | 17         | Per-filter config panel with on/off toggle      |
| 19 | TxDspPanel component                                             | P1       | @developer | [x]    | 16         | Co-located with PTT, button to open menu        |
| 20 | TxDspMenu component                                              | P1       | @developer | [x]    | 19         | Compressor presets, manual sliders, EQ, gate    |
| 21 | Integrate RxDspPillRow into main page layout                     | P0       | @developer | [x]    | 17, 18     | `routes/+page.svelte`                           |
| 22 | Integrate TxDspPanel into PTT area                               | P0       | @developer | [x]    | 19, 20     | `routes/+page.svelte`                           |
| 23 | Load DSP config from backend on radio connect                    | P0       | @developer | [x]    | 02, 10, 16 | Fetch GET on WS open, apply to chains           |
| 24 | Debounced save DSP config to backend on parameter change         | P0       | @developer | [x]    | 02, 23     | 500ms debounce, PATCH on change                 |
| 25 | Backend: unit tests for RxDspConfig and TxDspConfig validation   | P0       | @developer | [x]    | 01         | `tests/test_dsp_config.py`                      |
| 26 | Backend: integration tests for DSP config GET/PATCH              | P0       | @developer | [x]    | 02         | `tests/test_dsp_api.py`                         |
| 27 | Frontend: unit tests for RxDspChain node wiring                  | P0       | @developer | [x]    | 10         | Vitest, mock AudioContext                       |
| 28 | Frontend: unit tests for TxDspChain node wiring                  | P0       | @developer | [x]    | 16         | Vitest, mock AudioContext                       |

</details>

---

## Feature: v0.4.0 -- Security Hardening and Audit Remediations

Source: `/Users/wells/Projects/riglet/analysis/full_audit_20260329.md`

This feature addresses all Critical (C1-C3), High (H1-H4), and Medium (M1-M8) findings from the 2026-03-29 codebase audit. Low findings (L1-L8) are included where they have security implications or are trivially co-located with other fixes.

### Task Summary

| #  | Task                                                                          | Priority | Agent      | Status | Depends On | Notes                                                        |
|:---|:------------------------------------------------------------------------------|:---------|:-----------|:-------|:-----------|:-------------------------------------------------------------|
| 01 | Validate radio ID format in Pydantic model                                    | P0       | @developer | [x]    | --         | Fixes M1, M2, M3                                            |
| 02 | Validate mode strings against Hamlib mode list                                | P0       | @developer | [x]    | --         | Fixes C2 (mode injection)                                   |
| 03 | Sanitize all rigctld command string inputs                                    | P0       | @developer | [x]    | 02         | Fixes C2 (general injection)                                |
| 04 | Validate audio device names in config model                                   | P0       | @developer | [x]    | 01         | Fixes C3                                                    |
| 05 | Add asyncio.Lock for config mutations                                         | P0       | @developer | [x]    | --         | Fixes H4; main.py+dsp.py+system.py already done            |
| 06 | Fix float-to-Hz frequency conversion precision                                | P1       | @developer | [x]    | --         | Fixes L6                                                    |
| 07 | Fix S-meter calculation for over-S9 readings                                  | P1       | @developer | [x]    | --         | Fixes H2                                                    |
| 08 | Replace single SSE queue with broadcast pattern                               | P0       | @developer | [x]    | --         | Fixes H1                                                    |
| 09 | Fix setup wizard SSE no-op handler                                            | P1       | @developer | [x]    | 08         | Fixes M8                                                    |
| 10 | Close displaced waterfall WebSocket and kill orphaned subprocess              | P1       | @developer | [x]    | --         | Fixes M5                                                    |
| 11 | Flush pending DSP changes on DspPersistence.destroy()                         | P1       | @developer | [x]    | --         | Fixes M4                                                    |
| 12 | Token-based authentication: backend middleware and token management           | P0       | @developer | [ ]    | --         | SKIPPED per instructions                                    |
| 13 | Token-based authentication: frontend token handling                           | P0       | @developer | [ ]    | 12         | SKIPPED per instructions                                    |
| 14 | Remove duplicate RadioDep from audio.py                                       | P2       | @developer | [x]    | --         | Fixes L1                                                    |
| 15 | Extract DRY helper for RX DSP config application in +page.svelte             | P2       | @developer | [x]    | --         | Fixes L2                                                    |
| 16 | Remove dead code: _MONITOR_START and unused rx-float handler                 | P2       | @developer | [~]    | --         | Fixes L3, L7                                                |
| 17 | Remove or use itsdangerous dependency                                         | P1       | @developer | [~]    | 12         | Fixes M7; removing since auth skipped                       |
| 18 | Frequency bounds validation against band plan                                 | P2       | @developer | [x]    | --         | Fixes L5                                                    |
| 19 | Sanitize env file content (escape newlines in values)                         | P1       | @developer | [~]    | 01         | Fixes M2 (defense in depth alongside radio ID validation)   |
| 20 | Backend tests for new input validation and auth                               | P0       | @tester    | [~]    | 01-05, 12  | Tests for all Critical/High fixes (skipping auth tests)     |
| 21 | Frontend tests for auth token flow                                            | P1       | @tester    | [ ]    | 13         | SKIPPED per instructions                                    |

---

### Parallelization Strategy

**Wave 1** (no dependencies, all independent):
- Task 01: Radio ID validation
- Task 02: Mode string validation
- Task 05: Config mutation lock
- Task 06: Frequency precision fix
- Task 07: S-meter fix
- Task 08: SSE broadcast pattern
- Task 10: Waterfall WS cleanup
- Task 11: DspPersistence flush
- Task 12: Auth backend middleware
- Task 14: Remove duplicate RadioDep
- Task 15: DRY DSP config application
- Task 16: Remove dead code
- Task 18: Frequency bounds validation

**Wave 2** (depends on Wave 1 outputs):
- Task 03: Rigctld command sanitization (depends on 02)
- Task 04: Audio device name validation (depends on 01)
- Task 09: Fix wizard SSE handler (depends on 08)
- Task 13: Auth frontend handling (depends on 12)
- Task 17: itsdangerous dependency decision (depends on 12)
- Task 19: Env file content sanitization (depends on 01)

**Wave 3** (integration and testing):
- Task 20: Backend tests (depends on 01-05, 12)
- Task 21: Frontend auth tests (depends on 13)

---

### Task Descriptions

#### Task 01: Validate radio ID format in Pydantic model

**Audit refs:** M1 (path traversal in env file), M3 (systemd unit name injection)
**File:** `server/config.py`

Add a `field_validator` on `RadioConfig.id` that constrains the radio ID to a safe character set. This prevents path traversal in env file writes (`server/routers/system.py` line 40) and systemd unit name injection (line 82).

**Implementation:**
- Add to `RadioConfig`:
  ```python
  @field_validator("id")
  @classmethod
  def id_must_be_safe(cls, v: str) -> str:
      import re
      if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", v):
          raise ValueError(
              "Radio ID must be 1-63 chars, start with alphanumeric, "
              "and contain only lowercase letters, digits, hyphens, and underscores"
          )
      return v
  ```
- Pattern: `^[a-z0-9][a-z0-9_-]{0,62}$` -- lowercase alphanumeric start, then lowercase alphanumeric, hyphens, underscores. Max 63 chars (systemd unit name limit).

**Acceptance criteria:**
- `RadioConfig(id="radio-1", ...)` passes validation
- `RadioConfig(id="../../etc/passwd", ...)` raises `ValidationError`
- `RadioConfig(id="radio with spaces", ...)` raises `ValidationError`
- `RadioConfig(id="", ...)` raises `ValidationError`
- Existing tests still pass (existing test configs must use conforming IDs)

---

#### Task 02: Validate mode strings against Hamlib mode list

**Audit ref:** C2 (command injection via mode string)
**Files:** `server/state.py` (line 244), `server/routers/cat.py` (lines 84, 234)

Add server-side mode validation before any mode string reaches `send_command`. The `modes.py` module already provides `get_modes(hamlib_model)` which returns the curated list. Enforce it.

**Implementation:**

In `server/state.py`, add validation in `set_mode()`:
```python
async def set_mode(self, mode: str) -> None:
    from modes import get_modes
    allowed = get_modes(self.config.hamlib_model)
    if mode not in allowed:
        raise RigctldError(-1, f"Invalid mode {mode!r}. Allowed: {', '.join(allowed)}")
    ...
```

This protects both the REST endpoint (`cat.py` line 84-85) and the WebSocket handler (`cat.py` line 234) since both call `radio.set_mode()`.

**Acceptance criteria:**
- `set_mode("USB")` succeeds for a radio whose model supports USB
- `set_mode("USB\n+\\set_ptt 1")` raises `RigctldError`
- `set_mode("INVALID_MODE")` raises `RigctldError`
- Simulation mode also validates (reject before short-circuit)

---

#### Task 03: Sanitize all rigctld command string inputs

**Audit ref:** C2 (command injection via rigctld protocol)
**File:** `server/state.py`

Add a general-purpose input sanitizer for all values interpolated into rigctld commands. This is defense-in-depth on top of the per-field validation in Task 02.

**Implementation:**

Add a private helper to `RadioInstance`:
```python
@staticmethod
def _sanitize_rigctld_param(value: str) -> str:
    """Strip newlines, carriage returns, and null bytes from rigctld parameters."""
    sanitized = value.replace("\n", "").replace("\r", "").replace("\x00", "")
    if not sanitized or " " in sanitized:
        raise RigctldError(-1, f"Invalid rigctld parameter: {value!r}")
    return sanitized
```

Apply `_sanitize_rigctld_param()` in:
- `set_mode()` (line 250) -- on `mode` before interpolation
- `set_vfo()` (line 278) -- on `vfo` before interpolation (VFO is already allowlisted at the router level, but defense-in-depth here)

Integer/float parameters (`set_freq`, `set_ptt`, `set_ctcss`) are already type-coerced before interpolation, so they are not injectable. But add a comment explaining why.

**Acceptance criteria:**
- Strings containing `\n`, `\r`, or `\x00` are rejected with `RigctldError`
- Strings containing spaces are rejected
- Clean strings pass through unchanged
- All existing functionality still works

---

#### Task 04: Validate audio device names in config model

**Audit ref:** C3 (audio subprocess argument injection)
**File:** `server/config.py`

Add `field_validator` entries for `RadioConfig.audio_source` and `RadioConfig.audio_sink` to reject suspicious values.

**Implementation:**
```python
@field_validator("audio_source", "audio_sink")
@classmethod
def audio_device_must_be_safe(cls, v: str) -> str:
    if not v:  # empty is valid (means "not configured")
        return v
    # Reject control characters, shell metacharacters, and excessively long names
    import re
    if len(v) > 256:
        raise ValueError("Audio device name too long (max 256 chars)")
    if re.search(r"[\x00-\x1f\x7f;|&`$]", v):
        raise ValueError(f"Audio device name contains invalid characters: {v!r}")
    return v
```

**Acceptance criteria:**
- `audio_source="alsa_input.usb-Burr-Brown"` passes
- `audio_source=""` passes (not configured)
- `audio_source="device\nwith\nnewlines"` raises `ValidationError`
- `audio_source="$(evil)"` raises `ValidationError`

---

#### Task 05: Add asyncio.Lock for config mutations

**Audit ref:** H4 (race condition in config mutation)
**Files:** `server/main.py`, `server/routers/system.py`, `server/routers/dsp.py`

Create a shared `asyncio.Lock` on `app.state` and acquire it in all config-mutating endpoints.

**Implementation:**

In `server/main.py`, during lifespan setup:
```python
app.state.config_lock = asyncio.Lock()
```

In every endpoint that reads-then-writes `app.state.config`, wrap the critical section:

`server/routers/system.py` -- `post_config()` (line 122):
```python
async with request.app.state.config_lock:
    # ... existing validate + save + assign logic
```

`server/routers/dsp.py` -- `patch_dsp()` (line 46):
```python
async with request.app.state.config_lock:
    # ... existing read + merge + validate + save + assign logic
```

Also apply to any other config-mutating endpoints in `system.py` (e.g., preset endpoints at lines 298-332, 340-373, 382-393, 401-431 if they exist).

**Acceptance criteria:**
- Two concurrent PATCH requests to `/api/radios/{id}/dsp` with different fields both persist (no lost update)
- A concurrent `POST /api/config` and `PATCH /api/radios/{id}/dsp` serialize correctly
- No deadlocks under normal operation

---

#### Task 06: Fix float-to-Hz frequency conversion precision

**Audit ref:** L6 (float precision in frequency operations)
**File:** `server/state.py` (line 240)

**Change:**
```python
# Before:
hz = int(mhz * 1_000_000)

# After:
hz = round(mhz * 1_000_000)
```

This ensures `14.074` MHz becomes `14074000` Hz instead of `14073999` Hz.

**Acceptance criteria:**
- `14.074 * 1_000_000` produces `14074000` after `round()`
- `7.0` MHz produces `7000000` Hz (no regression)

---

#### Task 07: Fix S-meter calculation for over-S9 readings

**Audit ref:** H2 (S-meter loses over-S9 information)
**File:** `server/state.py` (line 318-336)

The current formula clamps S-units to 9 and discards "over S9" information. The S-meter display needs both the S-unit value (clamped 0-9) and the dB-over-S9 value for readings above S9.

**Change the return type and formula:**

```python
async def get_smeter(self) -> tuple[int, int, int]:
    """Return S-meter reading as (S-units 0-9, dB_over_s9, raw_dBm).

    S9 = -73 dBm; each S-unit = 6 dB.
    For readings above S9, s_units=9 and db_over contains the excess.
    """
    if self.simulation:
        return (5, 0, -103)
    raw = await self.send_command(r"+\get_level STRENGTH")
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped:
            try:
                dbm = float(stripped)
                raw_s = (dbm + 73) / 6 + 9
                s_units = max(0, min(9, round(raw_s)))
                db_over = max(0, round(dbm + 73)) if dbm > -73 else 0
                return (s_units, db_over, int(dbm))
            except ValueError:
                pass
    raise RigctldError(-8, f"Cannot parse get_level STRENGTH response: {raw!r}")
```

**Update all callers:**
- `server/state.py` poll loop where `get_smeter()` result is used -- update destructuring from 2-tuple to 3-tuple
- `server/routers/cat.py` WebSocket state push -- include `db_over` in the state message
- Frontend `SmeterDisplay` component -- display "S9+20" format when `db_over > 0`

**Files to update:**
- `server/state.py` -- return type and formula
- `server/routers/cat.py` -- WebSocket state message shape (if smeter is pushed there)
- `ui/src/lib/components/SmeterDisplay.svelte` -- render over-S9 readings

**Acceptance criteria:**
- -73 dBm returns `(9, 0, -73)` -- S9 exactly
- -121 dBm returns `(1, 0, -121)` -- S1
- -37 dBm returns `(9, 36, -37)` -- S9+36 dB
- -130 dBm returns `(0, 0, -130)` -- below S0, clamped
- Simulation returns `(5, 0, -103)`

---

#### Task 08: Replace single SSE queue with broadcast pattern

**Audit ref:** H1 (single-consumer SSE queue loses events for other clients)
**Files:** `server/devices.py`, `server/routers/devices.py`, `server/main.py`

Replace the single `asyncio.Queue` with a broadcast mechanism so all SSE subscribers receive every event.

**Implementation:**

In `server/devices.py`, add a `DeviceEventBroadcaster` class:
```python
class DeviceEventBroadcaster:
    """Fan-out device events to multiple SSE subscribers."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[DeviceEvent]] = []

    def subscribe(self) -> asyncio.Queue[DeviceEvent]:
        q: asyncio.Queue[DeviceEvent] = asyncio.Queue(maxsize=64)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[DeviceEvent]) -> None:
        with contextlib.suppress(ValueError):
            self._subscribers.remove(q)

    async def publish(self, event: DeviceEvent) -> None:
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # drop for slow consumers
```

In `server/main.py`:
- Replace `app.state.device_events = asyncio.Queue()` with `app.state.device_broadcaster = DeviceEventBroadcaster()`
- Update the udev monitor to call `broadcaster.publish(event)` instead of `queue.put(event)`

In `server/routers/devices.py` -- `get_device_events()`:
- Call `broadcaster.subscribe()` to get a per-client queue
- Use the per-client queue in the event generator
- Call `broadcaster.unsubscribe(q)` on disconnect (in a `finally` block)

**Acceptance criteria:**
- Two simultaneous SSE clients both receive the same device events
- Disconnecting one client does not affect the other
- Slow consumers are dropped rather than blocking publishers

---

#### Task 09: Fix setup wizard SSE no-op handler

**Audit ref:** M8 (SSE connection opened but events never processed)
**File:** `ui/src/routes/setup/+page.svelte` (lines 40-46)

The SSE connection in the setup wizard consumes events from the queue but does nothing with them. With the broadcast pattern from Task 08, this is less harmful (each client gets its own queue), but the handler should either be removed or made functional.

**Implementation:**
- Remove the top-level `$effect` that opens the no-op `EventSource`
- If device change reactivity is needed, move it into the individual wizard steps (`StepDetectRadios`, `StepMapAudio`) where the device lists are actually used -- have those steps open their own EventSource and re-fetch device lists on events
- Alternatively, if the steps already handle their own polling, simply remove the dead SSE connection

**Acceptance criteria:**
- No orphaned SSE connection opened at the wizard page level
- Device detection still works in wizard steps that need it
- No functional regression in the setup wizard flow

---

#### Task 10: Close displaced waterfall WebSocket and kill orphaned subprocess

**Audit ref:** M5 (waterfall WS not cleaned up on displacement)
**File:** `server/routers/waterfall.py` (lines 78-79)

**Implementation:**

Add displacement logic matching what `cat.py` already does for `ws_control`:
```python
# Before accepting the new connection:
if radio.ws_waterfall is not None:
    with contextlib.suppress(Exception):
        await radio.ws_waterfall.close()
```

Additionally, the existing capture subprocess must be terminated when a new client displaces the old one. The `capture_proc` is local to the WebSocket handler function, so the old handler's `finally` block should already kill it when its WebSocket is closed. Verify this by examining the handler's finally block. If the finally block does not terminate `capture_proc`, add termination logic.

**Acceptance criteria:**
- Opening a second waterfall WS closes the first one cleanly
- The orphaned `pw-record` process from the first connection is terminated
- No zombie processes accumulate when rapidly reconnecting

---

#### Task 11: Flush pending DSP changes on DspPersistence.destroy()

**Audit ref:** M4 (pending DSP changes dropped on navigation)
**File:** `ui/src/lib/dsp-persistence.ts`

**Change `destroy()` to flush instead of drop:**
```typescript
destroy(): void {
    if (this.rxTimer !== null) {
        clearTimeout(this.rxTimer);
        this.rxTimer = null;
        if (Object.keys(this.pendingRx).length > 0) {
            const patch = this.pendingRx;
            this.pendingRx = {};
            patchDspConfig(this.radioId, { rx: patch }).catch((e) => {
                console.warn('[DSP] Failed to flush RX DSP on destroy:', e);
            });
        }
    }
    if (this.txTimer !== null) {
        clearTimeout(this.txTimer);
        this.txTimer = null;
        if (Object.keys(this.pendingTx).length > 0) {
            const patch = this.pendingTx;
            this.pendingTx = {};
            patchDspConfig(this.radioId, { tx: patch }).catch((e) => {
                console.warn('[DSP] Failed to flush TX DSP on destroy:', e);
            });
        }
    }
}
```

Note: This is a fire-and-forget flush. The page may navigate away before the request completes. Consider using `navigator.sendBeacon` if the fetch is unreliable, but for a LAN application the standard fetch should complete fast enough.

**Acceptance criteria:**
- Adjusting a DSP knob and immediately navigating away persists the change
- If the PATCH fails, a warning is logged but no error is thrown

---

#### Task 12: Token-based authentication: backend middleware and token management

**Audit ref:** C1 (no authentication or authorization)
**Files:** `server/main.py`, `server/auth.py` (new file), `server/config.py`

Implement bearer token authentication using `itsdangerous` (already a dependency). The design targets a single-operator LAN deployment: a shared secret token rather than per-user accounts.

**Implementation:**

Create `server/auth.py`:
- On first startup, generate a random 32-byte token and store it in the config file under `auth.token` (or in a separate `~/.config/riglet/auth_token` file for separation)
- Provide `verify_token(token: str) -> bool` that does constant-time comparison
- Provide a FastAPI dependency `require_auth` that reads the `Authorization: Bearer <token>` header and raises 401 if invalid
- Provide a login endpoint `POST /api/auth/login` that accepts `{"token": "<token>"}` and returns `{"ok": true}` on success, 401 on failure. This lets the frontend validate the token before storing it.

Create auth middleware in `server/main.py`:
- Add `require_auth` as a dependency to all routers except:
  - `GET /api/status` (needed for health checks and the setup wizard's restart polling)
  - `POST /api/auth/login` (the login endpoint itself)
  - Static file serving (the SPA assets)
- WebSocket endpoints check the token via a query parameter (`?token=<token>`) since browsers cannot set custom headers on WebSocket connections

Add `auth_token: str = ""` field to `RigletConfig` (or a separate file). On first startup, if empty, generate and persist.

Display the token to the operator:
- Print it to stdout on startup: `"Auth token: <token> (see ~/.config/riglet/auth_token)"`
- Include it in `GET /api/status` response ONLY if the request is already authenticated (or on first-time setup when no token exists yet)

**Acceptance criteria:**
- Unauthenticated requests to `POST /api/config` return 401
- Unauthenticated requests to `GET /api/status` return 200 (exempt)
- Authenticated requests with valid `Authorization: Bearer <token>` succeed
- WebSocket connections with `?token=<valid>` succeed
- WebSocket connections without token are closed with code 4001
- Token is generated on first startup and persists across restarts

---

#### Task 13: Token-based authentication: frontend token handling

**Audit ref:** C1 (no authentication -- frontend half)
**Files:** `ui/src/lib/api.ts`, `ui/src/lib/websocket.ts`, `ui/src/routes/+page.svelte`, `ui/src/lib/stores/auth.ts` (new file)

**Implementation:**

Create `ui/src/lib/stores/auth.ts`:
- Svelte writable store holding the auth token
- Load from `localStorage` on init
- Provide `setToken(token: string)` and `clearToken()` helpers

Update `ui/src/lib/api.ts`:
- Add `Authorization: Bearer <token>` header to all fetch calls using the token from the auth store
- On 401 response from any API call, clear the stored token and redirect to a login prompt

Update `ui/src/lib/websocket.ts`:
- Append `?token=<token>` to WebSocket URLs

Create a login gate:
- In `+layout.svelte` or `+page.svelte`, check if a valid token exists in localStorage
- If not, show a simple login form (single text input for the token + submit button)
- On submit, call `POST /api/auth/login` to validate
- On success, store the token and proceed to the main UI
- On failure, show an error message

**Acceptance criteria:**
- First visit shows login form
- Entering valid token grants access and persists across page reloads
- Entering invalid token shows error
- API calls include the Bearer token
- WebSocket connections include the token as query parameter
- 401 from any API call clears the token and shows login form

---

#### Task 14: Remove duplicate RadioDep from audio.py

**Audit ref:** L1 (duplicate type alias)
**File:** `server/routers/audio.py` (line 47)

**Change:**
- Remove the local `RadioDep = Annotated[RadioInstance, Depends(get_radio)]` definition at line 47
- Import `RadioDep` from `deps` instead: `from deps import RadioDep`
- Verify existing imports: the file already imports `get_radio` from `deps` -- adjust to also import `RadioDep`

**Acceptance criteria:**
- `audio.py` uses `RadioDep` from `deps.py`
- No duplicate definition remains
- `uv run mypy .` passes clean

---

#### Task 15: Extract DRY helper for RX DSP config application in +page.svelte

**Audit ref:** L2 (duplicated DSP config application code)
**File:** `ui/src/routes/+page.svelte` (lines ~218-237 and ~286-334)

**Implementation:**
- Extract the repeated RX DSP config application block (calls to `rx.enableHighpass`, `rx.setHighpass`, etc.) into a standalone function, either:
  - A local function in `+page.svelte`: `function applyRxDspConfig(rx: RxDspChain, config: RxDspConfig): void`
  - Or a utility in `ui/src/lib/audio/rx-dsp-chain.ts`: `applyConfig(config: RxDspConfig): void` as a method on `RxDspChain`
- Replace both call sites (simulation branch and real-radio branch) with a call to the extracted function
- Do the same for TX DSP if the pattern is duplicated there

**Acceptance criteria:**
- Only one copy of the DSP config application logic exists
- Both code paths (simulation and real) produce identical behavior
- No TypeScript errors

---

#### Task 16: Remove dead code: _MONITOR_START and unused rx-float handler

**Audit refs:** L3 (dead `_MONITOR_START`), L7 (dead `rx-float` message handler)
**Files:** `server/devices.py` (line 266), `ui/src/lib/audio/audio-manager.ts` (rx-float handler)

**Implementation:**
- Remove `_MONITOR_START = time.monotonic()` from `server/devices.py` line 266 and its accompanying comment
- In `ui/src/lib/audio/audio-manager.ts`, locate the `workletNode.port.onmessage` handler that checks for `'rx-float'` message type and remove the dead branch

**Acceptance criteria:**
- No references to `_MONITOR_START` remain
- No `'rx-float'` message type check remains in the worklet port handler
- All tests pass, no TypeScript/mypy errors

---

#### Task 17: Remove or use itsdangerous dependency

**Audit ref:** M7 (unused dependency)
**File:** `server/pyproject.toml` (line 13)

**Decision depends on Task 12:**
- If Task 12 uses `itsdangerous` for token generation/signing, keep the dependency and this task is a no-op
- If Task 12 uses `secrets.token_urlsafe()` (stdlib) instead, remove `itsdangerous` from `pyproject.toml` dependencies and run `uv sync` to update the lockfile

**Acceptance criteria:**
- `itsdangerous` is either (a) imported and used by `auth.py` or (b) removed from `pyproject.toml`
- No unused dependency in the dependency list

---

#### Task 18: Frequency bounds validation against band plan

**Audit ref:** L5 (no frequency bounds check)
**Files:** `server/state.py`, `server/routers/cat.py`

**Implementation:**

In `server/state.py` `set_freq()`, add optional bounds checking:
```python
async def set_freq(self, mhz: float) -> None:
    if mhz <= 0:
        raise RigctldError(-1, f"Frequency must be positive, got {mhz}")
    if mhz > 500:  # No ham band above 450 MHz for HF/VHF rigs
        raise RigctldError(-1, f"Frequency {mhz} MHz exceeds maximum")
    ...
```

This is a sanity check, not a band-plan enforcement (which would be overly restrictive for SWL/receive-only use). The important thing is rejecting clearly invalid values (negative, zero, absurdly high).

**Acceptance criteria:**
- `set_freq(14.074)` succeeds
- `set_freq(0)` raises `RigctldError`
- `set_freq(-1)` raises `RigctldError`
- `set_freq(99999)` raises `RigctldError`

---

#### Task 19: Sanitize env file content (escape newlines in values)

**Audit ref:** M2 (env file content injection)
**File:** `server/routers/system.py` (lines 43-48)

**Implementation:**

Add a sanitization step when writing env file values. All values interpolated into the env file should have newlines, carriage returns, and null bytes stripped:

```python
def _sanitize_env_value(value: str | int) -> str:
    """Remove characters that could inject additional env vars."""
    s = str(value)
    return s.replace("\n", "").replace("\r", "").replace("\x00", "")
```

Apply to all interpolated values in `write_env_files()`:
```python
env_path.write_text(
    f"HAMLIB_MODEL={_sanitize_env_value(radio.hamlib_model)}\n"
    f"SERIAL_PORT={_sanitize_env_value(radio.serial_port)}\n"
    f"BAUD_RATE={_sanitize_env_value(radio.baud_rate)}\n"
    f"RIGCTLD_PORT={_sanitize_env_value(radio.rigctld_port)}\n"
    f"PTT_METHOD={_sanitize_env_value(radio.ptt_method)}\n",
    encoding="utf-8",
)
```

With Task 01 (radio ID validation) preventing path traversal and this task preventing content injection, the env file write path is fully hardened.

**Acceptance criteria:**
- Normal values pass through unchanged
- Values containing `\n` have them stripped silently
- Written env files contain exactly 5 lines (one per variable)

---

#### Task 20: Backend tests for new input validation and auth

**Audit refs:** All Critical/High fixes
**File:** `server/tests/test_security.py` (new file)

**Test cases:**

Radio ID validation:
- `test_radio_id_valid_formats`: "radio-1", "hf_rig", "a" all pass
- `test_radio_id_path_traversal`: "../../etc" raises ValidationError
- `test_radio_id_spaces`: "my radio" raises ValidationError
- `test_radio_id_empty`: "" raises ValidationError

Mode validation:
- `test_set_mode_valid`: valid mode for model succeeds
- `test_set_mode_injection`: mode with newline raises RigctldError
- `test_set_mode_unknown`: mode not in list raises RigctldError

Rigctld parameter sanitization:
- `test_sanitize_newline`: newline in param raises RigctldError
- `test_sanitize_null`: null byte in param raises RigctldError
- `test_sanitize_clean`: clean param passes through

Audio device validation:
- `test_audio_device_empty`: empty string passes
- `test_audio_device_valid`: normal PipeWire name passes
- `test_audio_device_injection`: name with shell chars raises ValidationError

Config lock:
- `test_concurrent_config_writes`: two concurrent PATCHes both persist their changes

Auth (if Task 12 is complete):
- `test_unauthenticated_config_post_401`: POST /config without token returns 401
- `test_authenticated_config_post_200`: POST /config with valid token succeeds
- `test_status_no_auth_required`: GET /status returns 200 without token
- `test_invalid_token_401`: wrong token returns 401

S-meter:
- `test_smeter_s9_exact`: -73 dBm -> (9, 0, -73)
- `test_smeter_over_s9`: -37 dBm -> (9, 36, -37)
- `test_smeter_s1`: -121 dBm -> (1, 0, -121)

Frequency:
- `test_freq_precision`: 14.074 MHz -> 14074000 Hz
- `test_freq_negative_rejected`: negative freq raises error
- `test_freq_zero_rejected`: zero freq raises error

**Acceptance criteria:**
- All tests pass with `uv run pytest tests/test_security.py`
- No regressions in existing test suite

---

#### Task 21: Frontend tests for auth token flow

**Audit ref:** C1 (frontend half)
**File:** `ui/src/lib/stores/auth.test.ts` (new file)

**Test cases:**
- `test_token_persists_to_localStorage`: `setToken("abc")` stores in localStorage
- `test_clearToken_removes`: `clearToken()` removes from localStorage
- `test_api_includes_bearer_header`: fetch calls include `Authorization: Bearer <token>`
- `test_401_clears_token`: a 401 response triggers token clearance

**Acceptance criteria:**
- All tests pass with `npm test`
