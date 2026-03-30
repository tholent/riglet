# Implementation Plan

## Feature: v0.6.0 Antenna Tuner Control

Add antenna tuner control to Riglet: built-in ATU tune cycle (`vfo_op TUNE`), ATU on/off toggle (`set_func TUNER`), external tuner workflow (server-side PTT + timer), live SWR feedback during tuning, and a dedicated `TuneButton.svelte` component integrated into `PttPanel.svelte`.

Reference: `.state/OVERVIEW.md` section "v0.6.0 -- Antenna Tuner Control"

## Task Summary

| # | Task | Priority | Agent | Status | Depends On | Notes |
|:--|:-----|:---------|:------|:-------|:-----------|:------|
| 1 | Add tuner state fields and capability caches to `RadioInstance` | P0 | @developer | [x] | -- | Backend state |
| 2 | Add `vfo_op_tune()` method to `RadioInstance` | P0 | @developer | [x] | 1 | Backend method |
| 3 | Add `set_tuner_func()` and `get_tuner_func()` methods to `RadioInstance` | P0 | @developer | [x] | 1 | Backend method |
| 4 | Add `external_tune()` method to `RadioInstance` | P0 | @developer | [x] | 1 | Backend method |
| 5 | Add `stop_tune()` method to `RadioInstance` | P0 | @developer | [x] | 2, 4 | Backend method |
| 6 | Add PTT/tune safety interlock to `set_ptt()` | P0 | @developer | [x] | 1 | Backend safety |
| 7 | Update `poll_once()` for SWR during tuning and tune completion detection | P0 | @developer | [x] | 1, 2 | Backend poll loop |
| 8 | Add tuner fields to `RadioManager.status()` and initial WS snapshot | P0 | @developer | [x] | 1 | Backend status |
| 9 | Handle tuner WS message types in `cat.py` | P0 | @developer | [x] | 2, 3, 4, 5 | Backend WS handler |
| 10 | Add tuner REST endpoints to `cat.py` | P1 | @developer | [x] | 2, 3, 4, 5 | Backend REST |
| 11 | Add backend tests for tuner state and methods | P0 | @developer | [x] | 1-7 | Backend tests |
| 12 | Add backend tests for tuner WS message handling | P0 | @developer | [x] | 9 | Backend tests |
| 13 | Add `tuning` and `tuner_enabled` to `RadioState` type | P0 | @developer | [x] | -- | Frontend types |
| 14 | Create `TuneButton.svelte` component | P0 | @developer | [x] | 13 | Frontend component |
| 15 | Integrate `TuneButton` into `PttPanel.svelte` | P0 | @developer | [x] | 14 | Frontend integration |
| 16 | Wire tuner state through `+page.svelte` | P0 | @developer | [x] | 13, 15 | Frontend wiring |

---

## Parallelization Strategy

**Wave 1** (no dependencies): Tasks 1, 13 -- backend state fields and frontend types can be done in parallel.

**Wave 2** (depends on Wave 1): Tasks 2, 3, 4, 6, 7, 8, 14 -- all backend methods and the frontend component depend only on their respective Wave 1 task.

**Wave 3** (depends on Wave 2): Tasks 5, 9, 10, 15 -- stop_tune needs 2+4; WS handler and REST need all methods; PttPanel integration needs the component.

**Wave 4** (depends on Wave 3): Tasks 11, 12, 16 -- tests and page-level wiring.

In practice, a single developer should execute sequentially: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10 -> 11 -> 12 -> 13 -> 14 -> 15 -> 16.

---

## Task Descriptions

### Task 1: Add tuner state fields and capability caches to `RadioInstance`

**File:** `server/state.py`

**Fields to add** in `RadioInstance.__init__()`, after the existing `# RF Gain / Squelch` block (after line 82):

```python
# Tuner state
self.tuning: bool = False
self.tuner_enabled: bool = False
self._tune_task: asyncio.Task[None] | None = None
self._tune_swr_count: int = 0  # consecutive polls with SWR < 2.0
self._tune_poll_count: int = 0  # poll cycles since tuning started

# Capability caches (None = unknown, True/False = tested)
self._supports_vfo_op_tune: bool | None = None
self._supports_tuner_func: bool | None = None
```

These fields track:
- `tuning` -- True while any tune cycle (built-in or external) is in progress.
- `tuner_enabled` -- mirrors the radio's ATU on/off state.
- `_tune_task` -- handle to the asyncio background task for external tune or built-in tune timeout.
- `_tune_swr_count` -- used by `poll_once()` to detect SWR convergence (3 consecutive below 2.0:1).
- `_tune_poll_count` -- counts poll cycles to throttle `get_func TUNER` queries (every 5th cycle).
- `_supports_vfo_op_tune` / `_supports_tuner_func` -- capability caches, set on first attempt.

**Verification:** `cd /Users/wells/Projects/riglet/server && uv run mypy . && uv run ruff check .`

---

### Task 2: Add `vfo_op_tune()` method to `RadioInstance`

**File:** `server/state.py`

**Method signature and location:** Add after `set_squelch()` (around line 433), before `get_smeter()`.

```python
async def vfo_op_tune(self) -> None:
```

**Behavior:**

1. If `self.ptt` is True, raise `RigctldError(-9, "Cannot tune while PTT is active")`.
2. If `self._supports_vfo_op_tune is False`, raise `RigctldError(-11, "Built-in tune not supported by this radio")`.
3. Set `self.tuning = True`, `self._tune_swr_count = 0`.
4. **Simulation mode:** Schedule an asyncio task (`self._tune_task`) that:
   - Sleeps 2 seconds.
   - Sets `self.swr` to 1.2 (simulating convergence).
   - Sets `self.tuning = False`.
   - Pushes `tune_complete` to `ws_control` if connected.
   - During the 2-second sleep, periodically update `self.swr` from 3.5 down to 1.2 (e.g., every 0.2s: 3.5, 2.8, 2.1, 1.6, 1.2).
   - Return after scheduling.
5. **Real mode:** Try `await self.send_command(r"+\vfo_op TUNE")`.
   - On success: set `self._supports_vfo_op_tune = True`. Schedule a background task (`self._tune_task`) that sleeps 10 seconds (timeout) then sets `self.tuning = False` if still tuning, and pushes `tune_complete` with `success=False`.
   - On `RigctldError` with code -4 or -11: set `self._supports_vfo_op_tune = False`, set `self.tuning = False`, re-raise.
   - On other `RigctldError`: set `self.tuning = False`, re-raise.

**Verification:** `cd /Users/wells/Projects/riglet/server && uv run mypy . && uv run ruff check .`

---

### Task 3: Add `set_tuner_func()` and `get_tuner_func()` methods to `RadioInstance`

**File:** `server/state.py`

**Methods to add** after `vfo_op_tune()`:

```python
async def set_tuner_func(self, enabled: bool) -> None:
```

1. If `self._supports_tuner_func is False`, raise `RigctldError(-11, "ATU toggle not supported by this radio")`.
2. **Simulation:** Set `self.tuner_enabled = enabled` and return.
3. **Real:** Send `+\set_func TUNER 1` or `+\set_func TUNER 0`.
   - On success: `self._supports_tuner_func = True`, `self.tuner_enabled = enabled`.
   - On `RigctldError` code -4 or -11: `self._supports_tuner_func = False`, re-raise.

```python
async def get_tuner_func(self) -> bool:
```

1. **Simulation:** Return `self.tuner_enabled`.
2. **Real:** Send `+\get_func TUNER`, parse response. `"1"` -> True, `"0"` -> False.
   - On `RigctldError`: return `self.tuner_enabled` (graceful fallback, same as `get_rf_gain` pattern).

**Verification:** `cd /Users/wells/Projects/riglet/server && uv run mypy . && uv run ruff check .`

---

### Task 4: Add `external_tune()` method to `RadioInstance`

**File:** `server/state.py`

**Method to add** after `get_tuner_func()`:

```python
async def external_tune(self, duration_s: float = 5.0) -> None:
```

**Behavior:**

1. Clamp `duration_s` to range [1.0, 15.0].
2. If `self.ptt` is True, raise `RigctldError(-9, "Cannot tune while PTT is active")`.
3. If `self.tuning` is True, raise `RigctldError(-9, "Tune cycle already in progress")`.
4. Set `self.tuning = True`, `self._tune_swr_count = 0`.
5. Create `self._tune_task` as an asyncio task running `_external_tune_loop(duration_s)`.

**Private method `_external_tune_loop(self, duration_s: float)`:**

```python
async def _external_tune_loop(self, duration_s: float) -> None:
```

1. `try/finally` block. The `finally` always calls `await self.set_ptt(False)` and sets `self.tuning = False`.
2. Call `await self.set_ptt(True)`.
3. **Simulation:** Loop in 0.5s increments for `duration_s` total. On each iteration, decrease `self.swr` linearly from 3.5 toward 1.2. Check if `self.ws_control is None` (WS disconnected); if so, break immediately (safety unkey).
4. **Real:** Same sleep loop with WS disconnect check. SWR is read by `poll_once()` concurrently.
5. After loop completes, set `self.swr` to final value. Push `tune_complete` to `ws_control` with `success = (self.swr < 2.0)` and `final_swr = self.swr`.

**Verification:** `cd /Users/wells/Projects/riglet/server && uv run mypy . && uv run ruff check .`

---

### Task 5: Add `stop_tune()` method to `RadioInstance`

**File:** `server/state.py`

**Method to add** after `_external_tune_loop()`:

```python
async def stop_tune(self) -> None:
```

**Behavior:**

1. If `self._tune_task is not None` and not done, cancel it and await with `contextlib.suppress(asyncio.CancelledError)`.
2. Set `self._tune_task = None`.
3. If `self.tuning` is still True (e.g., built-in tune without a task): set `self.tuning = False`.
4. If `self.ptt` is True (could be from external tune), call `await self.set_ptt(False)`.

This handles both built-in tune (cancel the timeout task) and external tune (cancel the carrier task, which triggers the try/finally PTT release).

**Verification:** `cd /Users/wells/Projects/riglet/server && uv run mypy . && uv run ruff check .`

---

### Task 6: Add PTT/tune safety interlock to `set_ptt()`

**File:** `server/state.py`

**Change:** At the top of `set_ptt()` (around line 295), before the simulation check, add:

```python
if active and self.tuning:
    raise RigctldError(-9, "Cannot engage PTT while tuning")
```

This prevents manual PTT while a tune cycle is in progress. The `external_tune()` method bypasses this by calling `set_ptt` only after setting `self.tuning = True` (so the check needs to distinguish internal vs. external calls). Two options:
- Option A: Add a `_tune_ptt` private bool flag. Set it True during `_external_tune_loop`, and the interlock skips when `_tune_ptt` is True.
- Option B: Have `_external_tune_loop` call `send_command` directly instead of `set_ptt`. This is simpler -- `_external_tune_loop` sends `+\set_ptt 1` and `+\set_ptt 0` directly, updates `self.ptt`, but does not go through the public `set_ptt` method.

**Recommendation:** Option B. The `_external_tune_loop` method calls `self.send_command(r"+\set_ptt 1")` / `self.send_command(r"+\set_ptt 0")` directly, updating `self.ptt` manually. In simulation mode, it just sets `self.ptt` directly. This avoids the interlock complexity.

**Verification:** `cd /Users/wells/Projects/riglet/server && uv run mypy . && uv run ruff check .`

---

### Task 7: Update `poll_once()` for SWR during tuning and tune completion detection

**File:** `server/state.py`

**Changes to `poll_once()` (around line 462):**

1. **SWR query condition:** Change the existing SWR query from `if self.ptt:` to `if self.ptt or self.tuning:`. This ensures SWR is polled during built-in tune cycles (where `self.ptt` may remain False but the radio is transmitting internally).

2. **During tuning, always include SWR in changes:** When `self.tuning` is True, include `changed["swr"] = new_swr` on every poll cycle (not just on change), so the UI gets smooth real-time SWR updates.

3. **Tune completion detection:** After the SWR query, when `self.tuning` is True:
   - If `new_swr < 2.0`: increment `self._tune_swr_count`.
   - Else: reset `self._tune_swr_count = 0`.
   - If `self._tune_swr_count >= 3`: tune has converged. Cancel `self._tune_task` if active. Set `self.tuning = False`. Push `{"type": "tune_complete", "success": True, "final_swr": new_swr}` to `ws_control`.

4. **Periodic tuner status poll:** Increment `self._tune_poll_count` each cycle. Every 5th cycle (`self._tune_poll_count % 5 == 0`), call `get_tuner_func()` wrapped in try/except. If the result differs from `self.tuner_enabled`, update and include in `changed`.

**Verification:** `cd /Users/wells/Projects/riglet/server && uv run mypy . && uv run ruff check .`

---

### Task 8: Add tuner fields to `RadioManager.status()` and initial WS snapshot

**File:** `server/state.py` and `server/routers/cat.py`

**Changes in `state.py`:** In `RadioManager.status()` (around line 611), add to the dict comprehension:
```python
"tuning": inst.tuning,
"tuner_enabled": inst.tuner_enabled,
```

**Changes in `cat.py`:** In the initial state snapshot `send_json` (around line 215), add:
```python
"tuning": radio.tuning,
"tuner_enabled": radio.tuner_enabled,
"swr": radio.swr,
```

Note: `swr` is already tracked but not currently sent in the initial snapshot. Include it now since the TuneButton needs it on connect.

**Verification:** `cd /Users/wells/Projects/riglet/server && uv run mypy . && uv run ruff check .`

---

### Task 9: Handle tuner WS message types in `cat.py`

**File:** `server/routers/cat.py`

**Add four new `elif` branches** in the WS message handler loop (before the `else` unknown-type branch, around line 271):

1. **`tune_start`:**
   ```python
   elif msg_type == "tune_start":
       method = str(msg.get("method", "builtin"))
       if method == "builtin":
           await radio.vfo_op_tune()
           await websocket.send_json({"type": "state", "tuning": radio.tuning})
       elif method == "external":
           duration = float(msg.get("duration", 5.0))
           await radio.external_tune(duration)
           await websocket.send_json({"type": "state", "tuning": radio.tuning, "ptt": radio.ptt})
       else:
           await websocket.send_json({"type": "error", "code": "invalid_method", "message": f"Unknown tune method: {method!r}"})
   ```

2. **`tune_stop`:**
   ```python
   elif msg_type == "tune_stop":
       await radio.stop_tune()
       await websocket.send_json({"type": "state", "tuning": radio.tuning, "ptt": radio.ptt})
   ```

3. **`tuner_enable`:**
   ```python
   elif msg_type == "tuner_enable":
       await radio.set_tuner_func(True)
       await websocket.send_json({"type": "state", "tuner_enabled": radio.tuner_enabled})
   ```

4. **`tuner_disable`:**
   ```python
   elif msg_type == "tuner_disable":
       await radio.set_tuner_func(False)
       await websocket.send_json({"type": "state", "tuner_enabled": radio.tuner_enabled})
   ```

The existing `RigctldError` catch block at the bottom of the try already handles errors from these methods, sending `{"type": "error", ...}` back to the client.

**Verification:** `cd /Users/wells/Projects/riglet/server && uv run mypy . && uv run ruff check .`

---

### Task 10: Add tuner REST endpoints to `cat.py`

**File:** `server/routers/cat.py`

**New request models:**
```python
class TuneRequest(BaseModel):
    method: Literal["builtin", "external"] = "builtin"
    duration: float = 5.0

class TunerRequest(BaseModel):
    enabled: bool
```

**New endpoints:**

1. `POST /radio/{radio_id}/cat/tune` -- body `TuneRequest`. Calls `radio.vfo_op_tune()` or `radio.external_tune(body.duration)`. Returns `{"tuning": radio.tuning}`.

2. `POST /radio/{radio_id}/cat/tune/stop` -- no body. Calls `radio.stop_tune()`. Returns `{"tuning": radio.tuning}`.

3. `POST /radio/{radio_id}/cat/tuner` -- body `TunerRequest`. Calls `radio.set_tuner_func(body.enabled)`. Returns `{"enabled": radio.tuner_enabled}`.

4. `GET /radio/{radio_id}/cat/tuner` -- no body. Calls `radio.get_tuner_func()`. Returns `{"enabled": result}`.

Follow the existing error handling pattern (try/except with 503 for radio unavailable).

**Verification:** `cd /Users/wells/Projects/riglet/server && uv run mypy . && uv run ruff check .`

---

### Task 11: Add backend tests for tuner state and methods

**File:** `server/test_tuner.py` (new file)

Uses `pytest` with `asyncio_mode = "auto"`. Import `RadioInstance`, `RadioConfig`, `RigctldError` from `state` and `config`.

**Helper:** Create a simulated `RadioInstance` using a `RadioConfig` with `type="simulated"`.

**Tests:**

1. `test_tuner_state_defaults` -- Assert `radio.tuning == False`, `radio.tuner_enabled == False`, `radio._supports_vfo_op_tune is None`, `radio._supports_tuner_func is None`.

2. `test_vfo_op_tune_simulation` -- Call `await radio.vfo_op_tune()`. Assert `radio.tuning == True`. Wait 2.5 seconds. Assert `radio.tuning == False` and `radio.swr` is approximately 1.2.

3. `test_vfo_op_tune_rejects_during_ptt` -- Set `radio.ptt = True`. Call `vfo_op_tune()`, assert raises `RigctldError` with code -9.

4. `test_set_tuner_func_simulation` -- Call `await radio.set_tuner_func(True)`. Assert `radio.tuner_enabled == True`. Call `await radio.set_tuner_func(False)`. Assert `radio.tuner_enabled == False`.

5. `test_get_tuner_func_simulation` -- Set `radio.tuner_enabled = True`. Assert `await radio.get_tuner_func() == True`.

6. `test_external_tune_simulation` -- Call `await radio.external_tune(2.0)`. Assert `radio.tuning == True` and `radio.ptt == True`. Wait 2.5 seconds. Assert `radio.tuning == False` and `radio.ptt == False`.

7. `test_external_tune_duration_clamped` -- Call `external_tune(0.5)`, verify duration is clamped to 1.0 (tune completes in ~1 second, not 0.5). Call `external_tune(20.0)`, verify clamped to 15.0.

8. `test_external_tune_rejects_during_ptt` -- Set `radio.ptt = True`. Assert `external_tune()` raises `RigctldError` with code -9.

9. `test_stop_tune_cancels_external` -- Start `external_tune(10.0)`. Wait 0.5s. Call `stop_tune()`. Assert `radio.tuning == False` and `radio.ptt == False`.

10. `test_ptt_rejects_during_tuning` -- Set `radio.tuning = True`. Call `set_ptt(True)`, assert raises `RigctldError` with code -9.

11. `test_status_includes_tuner_fields` -- Create a `RadioManager`, call `startup()` with a simulated config. Assert `status()` output includes `tuning` and `tuner_enabled` keys.

**Verification:** `cd /Users/wells/Projects/riglet/server && uv run pytest test_tuner.py -v`

---

### Task 12: Add backend tests for tuner WS message handling

**File:** `server/test_tuner.py` (append to same file, or `server/test_tuner_ws.py`)

Uses `httpx.ASGITransport` and `httpx.AsyncClient` with the FastAPI `app` to test WebSocket endpoints. Follow whatever pattern exists in other test files, or use `TestClient` from `starlette.testclient`.

**Tests:**

1. `test_ws_initial_state_includes_tuner_fields` -- Connect to `/api/radio/{id}/ws/control`. Read initial state message. Assert it contains `tuning`, `tuner_enabled`, and `swr` keys.

2. `test_ws_tune_start_builtin` -- Send `{"type": "tune_start", "method": "builtin"}`. Assert response contains `{"type": "state", "tuning": true}`.

3. `test_ws_tune_start_external` -- Send `{"type": "tune_start", "method": "external", "duration": 2}`. Assert response contains `tuning: true, ptt: true`.

4. `test_ws_tune_stop` -- Start a tune, then send `{"type": "tune_stop"}`. Assert response has `tuning: false`.

5. `test_ws_tuner_enable` -- Send `{"type": "tuner_enable"}`. Assert response has `tuner_enabled: true`.

6. `test_ws_tuner_disable` -- Send `{"type": "tuner_disable"}`. Assert response has `tuner_enabled: false`.

7. `test_ws_tune_rejected_during_ptt` -- Send `{"type": "ptt", "active": true}`, then `{"type": "tune_start", "method": "builtin"}`. Assert error response with "Cannot tune while PTT is active".

**Verification:** `cd /Users/wells/Projects/riglet/server && uv run pytest test_tuner.py -v` (or `test_tuner_ws.py`)

---

### Task 13: Add `tuning` and `tuner_enabled` to `RadioState` type

**File:** `ui/src/lib/types.ts`

**Change:** Add two optional fields to the `RadioState` interface (after `squelch?: number;`, line 48):

```typescript
tuning?: boolean;
tuner_enabled?: boolean;
```

**Verification:** `cd /Users/wells/Projects/riglet/ui && npm run build`

---

### Task 14: Create `TuneButton.svelte` component

**File:** `ui/src/lib/components/TuneButton.svelte` (new file)

**Props interface:**
```typescript
interface Props {
    ptt: boolean;
    tuning: boolean;
    tunerEnabled: boolean;
    swr: number;
    controlWs: ControlWebSocket | null;
}
```

**Internal state:**
- `let tuneMethod: 'builtin' | 'external' = $state(loadMethod())` -- persisted in `localStorage` under key `riglet:tuneMethod`.
- `let externalDuration: number = $state(5)` -- seconds, persisted in `localStorage` under key `riglet:tuneDuration`.
- `let tuneComplete: boolean = $state(false)` -- brief flash state after tune completes.
- `let tuneSuccess: boolean = $state(false)` -- whether last tune was successful.

**Functions:**
- `startTune()`: If `ptt` is true, return (disabled). Send `{ type: "tune_start", method: tuneMethod, duration: externalDuration }` via `controlWs.send()`.
- `stopTune()`: Send `{ type: "tune_stop" }` via `controlWs.send()`.
- `toggleTuner()`: Send `{ type: tunerEnabled ? "tuner_disable" : "tuner_enable" }` via `controlWs.send()`.
- `loadMethod()` / `saveMethod()`: Read/write `localStorage` for method preference.
- `swrColor(swr: number) -> string`: Returns CSS color: green if < 1.5, yellow if < 2.5, orange if < 3.5, red otherwise.

**Effects:**
- `$effect` watching for incoming `tune_complete` messages: The parent page will set a `tuneComplete` event prop or the component listens via a callback. Alternatively, the component watches `tuning` transitioning from `true` to `false` and shows a brief flash. Use `$effect.pre` to detect the transition.

**Template structure:**
```
<div class="tune-wrap">
  <button class="tune-btn" (idle | tuning | disabled states)>
    {tuning ? 'TUNING' : 'TUNE'}
  </button>

  <div class="tune-controls">
    <!-- Method toggle: two small pills "INT" / "EXT" -->
    <div class="method-toggle">...</div>

    <!-- ATU toggle pill (same pattern as VOX toggle in PttButton) -->
    <button class="atu-btn" class:active={tunerEnabled}>ATU</button>
  </div>

  <!-- SWR readout, shown during tuning or TX -->
  {#if tuning || ptt}
    <div class="swr-readout" style="color: {swrColor(swr)}">
      {swr.toFixed(1)}:1
    </div>
  {/if}

  <!-- External duration selector when method is "external" -->
  {#if tuneMethod === 'external'}
    <div class="duration-select">
      {#each [3, 5, 10] as d}
        <button class:active={externalDuration === d} onclick={() => { externalDuration = d; }}>{d}s</button>
      {/each}
    </div>
  {/if}
</div>
```

**Styling:**
- Tune button: 72x72px circle (smaller than PTT's 96x96). Amber/gold border (`#d4a017`). Active/tuning state: amber background with pulse animation.
- Disabled (PTT active): `opacity: 0.4`, `pointer-events: none`, `cursor: not-allowed`.
- ATU pill: same style as VOX button in `PttButton.svelte` (green when active, dim when off).
- Method pills: small inline toggle, `font-size: 0.7rem`.
- SWR readout: monospace, `font-size: 0.85rem`, color-coded.

**Keyboard accessibility:**
- Tune button: `Enter`/`Space` to start, `Escape` to abort.
- ATU toggle: `Enter`/`Space`.
- All elements have `aria-label` and `aria-pressed` where applicable.

**Verification:** `cd /Users/wells/Projects/riglet/ui && npm run build`

---

### Task 15: Integrate `TuneButton` into `PttPanel.svelte`

**File:** `ui/src/lib/components/PttPanel.svelte`

**Changes:**

1. **Import** `TuneButton` from `./TuneButton.svelte`.

2. **Add new props** to the `Props` interface:
   ```typescript
   tuning: boolean;
   tunerEnabled: boolean;
   swr: number;
   ```

3. **Destructure** new props: `tuning, tunerEnabled, swr`.

4. **Add `<div class="ptt-tune">` section** in the template between `.ptt-left` and `.ptt-dsp`:
   ```svelte
   <div class="ptt-tune">
       <TuneButton {ptt} {tuning} {tunerEnabled} {swr} {controlWs} />
   </div>
   ```

5. **Add CSS** for `.ptt-tune`:
   ```css
   .ptt-tune {
       display: flex;
       align-items: center;
       justify-content: center;
       padding: 10px 12px;
       flex-shrink: 0;
       border-right: 1px solid #222;
   }
   ```

The resulting layout order is: `[ LUFS? ] [ PTT ] [ TUNE ] [ TX DSP ] [ LUFS? ]`.

**Verification:** `cd /Users/wells/Projects/riglet/ui && npm run build`

---

### Task 16: Wire tuner state through `+page.svelte`

**File:** `ui/src/routes/+page.svelte`

**Changes:**

1. **Extend initial radio state** (around line 31): Add defaults to the radio object:
   ```typescript
   tuning: false,
   tuner_enabled: false,
   ```

2. **Handle incoming WS state** in `handleControlMessage()` (around line 183, after the `squelch` handler):
   ```typescript
   if (m.tuning !== undefined) radio = { ...radio, tuning: m.tuning as boolean };
   if (m.tuner_enabled !== undefined) radio = { ...radio, tuner_enabled: m.tuner_enabled as boolean };
   ```

3. **Handle `tune_complete` message:** Add a check in `handleControlMessage` for `m.type === 'tune_complete'`. This is a separate message type (not `state`), so it needs handling. The simplest approach: the control WS `onmessage` callback receives all JSON messages. When `m.type === 'tune_complete'`, the existing `handleControlMessage` does not process it (it only handles `state` type). Two options:
   - Extend `handleControlMessage` to also handle `tune_complete` by setting a transient state (e.g., `tuneCompleteResult`).
   - Or let the TuneButton detect tune completion by watching `tuning` transition from true to false.

   **Recommendation:** The simplest approach is to let `tune_complete` set `radio.tuning = false` (which the state message already does) and let `TuneButton` detect the transition. No explicit `tune_complete` handler needed in `+page.svelte` -- the `state` push that accompanies tune completion already sets `tuning: false`.

4. **Pass new props to PttPanel** in both the narrow layout (around line 436) and the dynamic layout (around line 483). Add to each `<PttPanel>` instance:
   ```svelte
   tuning={radio.tuning ?? false}
   tunerEnabled={radio.tuner_enabled ?? false}
   swr={radio.swr ?? 1.0}
   ```

   There are exactly two `<PttPanel>` instances:
   - Narrow layout (around line 436)
   - Dynamic layout `panel.component === 'ptt'` (around line 483)

**Verification:** `cd /Users/wells/Projects/riglet/ui && npm run build`. End-to-end: open the UI in simulation mode, the Tune button appears next to PTT, clicking starts a simulated tune cycle, SWR readout appears and converges, ATU toggle works, method selector persists.
