# Implementation Plan

## Feature: RF Gain / Squelch Knob

Add a combined RF Gain / Squelch control knob to the UI, backed by Hamlib `RF` and `SQL` level commands via rigctld.

## Task Summary

| # | Task | Priority | Agent | Status | Depends On | Notes |
|:--|:-----|:---------|:------|:-------|:-----------|:------|
| 1 | Add `rf_gain` and `squelch` fields + methods to `RadioInstance` | P0 | @developer | [~] | — | Backend state |
| 2 | Add `rf_gain` and `squelch` to `RadioManager.status()` | P0 | @developer | [~] | 1 | Status output |
| 3 | Handle `rf_gain` and `squelch` in control WebSocket | P0 | @developer | [~] | 1 | WS handler |
| 4 | Add backend tests for RF gain and squelch | P0 | @developer | [~] | 1, 3 | Tests |
| 5 | Add `rf_gain` and `squelch` to `RadioState` type | P0 | @developer | [~] | — | Frontend types |
| 6 | Create `RfSqlKnob.svelte` component | P0 | @developer | [~] | 5 | New component |
| 7 | Wire `RfSqlKnob` into `AudioControls.svelte` | P0 | @developer | [~] | 6 | Integration |
| 8 | Wire state through `+page.svelte` | P0 | @developer | [~] | 5, 7 | Page wiring |

---

## Parallelization Strategy

**Wave 1** (no dependencies): Tasks 1, 5 -- backend state fields and frontend types can be done in parallel.

**Wave 2** (depends on Wave 1): Tasks 2, 3, 6 -- manager status, WS handler, and Svelte component can all proceed in parallel once their respective Wave 1 dependency is done.

**Wave 3** (depends on Wave 2): Tasks 4, 7 -- backend tests and AudioControls integration.

**Wave 4** (depends on Wave 3): Task 8 -- page-level wiring.

In practice, a single developer should execute sequentially: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8.

---

## Task Descriptions

### Task 1: Add `rf_gain` and `squelch` fields + methods to `RadioInstance`

**File:** `server/state.py`

**Fields to add** (alongside existing `rx_volume`, `tx_gain`, `nr_level` block around line 74):
```python
self.rf_gain: int = 50
self.squelch: int = 0
```

**Methods to add** (after `get_smeter` / before `poll_once`, following the `get_swr`/`get_ctcss` pattern):

1. `async def get_rf_gain(self) -> int` -- Query `+\get_level RF`. Rigctld returns a float 0.0-1.0. Convert to int 0-100 via `round(float_val * 100)`. In simulation mode, return `self.rf_gain`. If the rig returns an error (feature not available), catch `RigctldError` and return the current stored value.

2. `async def set_rf_gain(self, level: int) -> None` -- Validate `level` is 0-100 (raise `RigctldError(-1, ...)` if not). Send `+\set_level RF {level / 100.0:.2f}`. In simulation mode, just store the value. Update `self.rf_gain = level` after success.

3. `async def get_squelch(self) -> int` -- Query `+\get_level SQL`. Same float-to-int conversion as RF gain. In simulation mode, return `self.squelch`.

4. `async def set_squelch(self, level: int) -> None` -- Validate `level` is 0-100. Send `+\set_level SQL {level / 100.0:.2f}`. In simulation mode, just store. Update `self.squelch = level` after success.

**Parsing pattern:** Follow `get_swr()` -- iterate `raw.splitlines()`, try `float(stripped)` on non-empty lines, convert to int 0-100.

**Verification:** `uv run mypy .` and `uv run ruff check .` pass clean.

---

### Task 2: Add `rf_gain` and `squelch` to `RadioManager.status()`

**File:** `server/state.py`

**Change:** In `RadioManager.status()` (line 536-553), add two keys to the dict comprehension:
```python
"rf_gain": inst.rf_gain,
"squelch": inst.squelch,
```

Place them after the `"ctcss_tone"` entry.

**Verification:** `uv run mypy .` passes. The `/api/status` endpoint now includes these fields in its response.

---

### Task 3: Handle `rf_gain` and `squelch` in control WebSocket

**File:** `server/routers/cat.py`

**Changes:**

1. **Initial state snapshot** (line 215-223): Add `"rf_gain": radio.rf_gain` and `"squelch": radio.squelch` to the `send_json` dict in the `ws_control` handler, after the `"online"` field.

2. **Message handler** (inside the `while True` loop, before the `else` unknown-type branch around line 263): Add two new `elif` branches:

   ```python
   elif msg_type == "rf_gain":
       await radio.set_rf_gain(int(msg["level"]))
       await websocket.send_json({"type": "state", "rf_gain": radio.rf_gain})
   elif msg_type == "squelch":
       await radio.set_squelch(int(msg["level"]))
       await websocket.send_json({"type": "state", "squelch": radio.squelch})
   ```

   These follow the exact same echo-state-after-set pattern used by `freq`, `mode`, `ptt`, `vfo`, and `ctcss`.

**Verification:** `uv run mypy .` and `uv run ruff check .` pass clean.

---

### Task 4: Add backend tests for RF gain and squelch

**File:** `server/tests/test_state.py` (simulation tests) and `server/tests/test_cat.py` (WebSocket tests)

**test_state.py -- add after existing simulation tests:**

1. `test_rf_gain_simulation_default` -- Create a simulated `RadioInstance`, assert `radio.rf_gain == 50`.

2. `test_set_rf_gain_simulation` -- Call `await radio.set_rf_gain(75)`, assert `radio.rf_gain == 75`.

3. `test_set_rf_gain_simulation_bounds` -- Call `set_rf_gain(-1)` and `set_rf_gain(101)`, assert both raise `RigctldError`.

4. `test_get_rf_gain_simulation` -- Call `await radio.get_rf_gain()`, assert returns `radio.rf_gain`.

5. `test_squelch_simulation_default` -- Assert `radio.squelch == 0`.

6. `test_set_squelch_simulation` -- Call `await radio.set_squelch(30)`, assert `radio.squelch == 30`.

7. `test_get_squelch_simulation` -- Call `await radio.get_squelch()`, assert returns `radio.squelch`.

Use the existing `make_radio_config()` helper. Create simulated instances the same way existing tests do (set `config.type = "simulated"` or create with type="simulated").

**test_cat.py -- add WebSocket test:**

8. `test_ws_rf_gain_echo` -- Connect to `/api/radio/r1/ws/control` via `httpx` AsyncClient's WebSocket support (or the existing pattern in test_cat.py). Send `{"type": "rf_gain", "level": 80}`. Assert the response contains `{"type": "state", "rf_gain": 80}`.

9. `test_ws_squelch_echo` -- Same pattern, send `{"type": "squelch", "level": 25}`, assert response.

10. `test_ws_initial_state_includes_rf_squelch` -- Connect, read the initial state message, assert it contains `rf_gain` and `squelch` keys.

**Verification:** `uv run pytest` passes. All new tests green.

---

### Task 5: Add `rf_gain` and `squelch` to `RadioState` type

**File:** `ui/src/lib/types.ts`

**Change:** Add two optional fields to the `RadioState` interface (after `ctcss_tone`):
```typescript
rf_gain?: number;
squelch?: number;
```

**Verification:** `npm run build` passes with no type errors.

---

### Task 6: Create `RfSqlKnob.svelte` component

**File:** `ui/src/lib/components/RfSqlKnob.svelte` (new file)

**Props interface:**
```typescript
interface Props {
    rfGain: number;
    squelch: number;
    mode: string;
    controlWs: ControlWebSocket | null;
}
```

**Behavior:**

- Internal toggle state: `let activeKnob: 'rf' | 'sql' = $state('rf');` -- determines which value the knob controls.
- Derive `value`, `label`, and `defaultValue` from `activeKnob`:
  - RF Gain: value = `rfGain`, label = "RF Gain", default = 50
  - Squelch: value = `squelch`, label = "Squelch", default = 0
- Render one `Knob` component (reuse from `./Knob.svelte`) with `size={72}`, `min={0}`, `max={100}`, `step={5}`.
- `onchange` handler: send `{ type: "rf_gain", level: v }` or `{ type: "squelch", level: v }` via `controlWs.send()`.
- `onclick` handler: toggle `activeKnob` between `'rf'` and `'sql'`.
- Auto-follow mode transitions: use `$effect` watching `mode`. When mode changes to `FM` or `AM`, switch to `'sql'`; when mode changes to `USB`, `LSB`, `CW`, `RTTY`, or `FT8`, switch to `'rf'`. This is a UX convenience, not enforced -- the user can always click to toggle.

**Template:** Single `<Knob>` wrapped in a `<div>` with an aria-label. The label on the knob itself indicates which parameter is active.

**Styling:** Minimal -- match existing `AudioControls` flex layout pattern.

**Verification:** `npm run build` passes.

---

### Task 7: Wire `RfSqlKnob` into `AudioControls.svelte`

**File:** `ui/src/lib/components/AudioControls.svelte`

**Changes:**

1. Add new props to the `Props` interface:
   ```typescript
   rfGain?: number;
   squelch?: number;
   mode?: string;
   controlWs?: ControlWebSocket | null;
   ```

2. Destructure new props with defaults: `rfGain = 50, squelch = 0, mode = 'USB', controlWs = null`.

3. Import `RfSqlKnob` from `./RfSqlKnob.svelte`.

4. Import `ControlWebSocket` type from `$lib/websocket.js`.

5. Add `<RfSqlKnob>` after the existing AF Gain `<Knob>` inside `div.audio-controls`:
   ```svelte
   <RfSqlKnob {rfGain} {squelch} {mode} {controlWs} />
   ```

**Verification:** `npm run build` passes.

---

### Task 8: Wire state through `+page.svelte`

**File:** `ui/src/routes/+page.svelte`

**Changes:**

1. **Handle incoming WS state** in `handleControlMessage` (around line 173): Add two lines after the `ctcss_tone` handler:
   ```typescript
   if (m.rf_gain !== undefined) radio = { ...radio, rf_gain: m.rf_gain as number };
   if (m.squelch !== undefined) radio = { ...radio, squelch: m.squelch as number };
   ```

2. **Pass props to AudioControls** -- everywhere `<AudioControls>` is rendered (narrow layout around line 419, and dynamic layout around line 464), add props:
   ```svelte
   rfGain={radio.rf_gain ?? 50}
   squelch={radio.squelch ?? 0}
   mode={radio.mode}
   {controlWs}
   ```

   There are exactly two `<AudioControls>` instances in the template:
   - Narrow layout (line 419): `<AudioControls {radioId} {rxVolume} {txGain} audioManager={audioMgr} />`
   - Dynamic layout (line 464): `<AudioControls {radioId} {rxVolume} {txGain} audioManager={audioMgr} />`

   Both need the four new props added.

**Verification:** `npm run build` passes. Full end-to-end: open the UI in simulation mode, the RF Gain / Squelch knob appears next to the AF Gain knob, clicking toggles between RF and SQL, dragging sends WS messages, and the knob reflects state pushed from the backend.
