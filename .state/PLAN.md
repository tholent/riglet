# Riglet -- Implementation Plan

> v0.1.0 is complete (phases 1-11 fully implemented and verified).
> v0.2.0 plan follows. See `.state/OVERVIEW.md` for system design and v0.2.0 goals.

---

## Feature: v0.2.0 -- Rich Visualization, Client-Side DSP, Enhanced Controls

## Task Summary

| # | Task | Priority | Agent | Status | Depends On | Notes |
|:--|:-----|:---------|:------|:-------|:-----------|:------|
| 1 | Region-aware band plan data module | P0 | @developer | [~] in-process | -- | Backend + frontend data |
| 2 | Config schema: operator.region, radio.type, radio.bands, presets | P0 | @developer | [~] in-process | -- | Pydantic models + validation |
| 3 | Config schema frontend types | P0 | @developer | [~] in-process | 2 | TypeScript types match new schema |
| 4 | Explicit simulation radio type | P0 | @developer | [~] in-process | 2 | RadioInstance type-aware behavior |
| 5 | Extended CAT: VFO, SWR, CTCSS | P1 | @developer | [x] complete | 4 | New rigctld commands in state.py + cat router |
| 6 | Curated mode list per radio | P1 | @developer | [x] complete | 5 | Hamlib model -> mode list mapping |
| 7 | Frequency presets API | P1 | @developer | [~] in-process | 2 | REST CRUD for presets in config |
| 8 | Band plan API endpoint | P1 | @developer | [~] in-process | 1 | GET /api/bandplan |
| 9 | Theme infrastructure (CSS custom properties) | P0 | @developer | [~] in-process | -- | Light/dark theme system |
| 10 | Accessibility foundation | P0 | @developer | [~] in-process | 9 | ARIA roles, keyboard nav, skip links |
| 11 | Scroll-wheel mixin for dial controls | P1 | @developer | [~] in-process | 10 | Reusable Svelte action |
| 12 | Visualization renderer interface | P0 | @developer | [~] in-process | -- | Pluggable canvas renderer abstraction |
| 13 | Refactor Waterfall to use renderer interface | P0 | @developer | [x] complete | 12 | Migrate existing waterfall |
| 14 | Spectrum scope renderer | P1 | @developer | [x] complete | 12 | Freq vs amplitude overlay |
| 15 | Oscilloscope renderer | P1 | @developer | [x] complete | 12 | Time-domain waveform |
| 16 | Constellation renderer | P2 | @developer | [~] in-process | 12 | X-Y plot for I/Q or L/R |
| 17 | Phase/correlation meter renderer | P2 | @developer | [~] in-process | 12 | Correlation coefficient display |
| 41 | 3D spectrogram renderer | P1 | @developer | [~] in-process | 12 | WebGL freq-time-amplitude perspective view |
| 18 | Visualization mode switcher UI | P1 | @developer | [~] in-process | 13, 14 | Toggle between visualization modes |
| 19 | LUFS audio meter component | P1 | @developer | [~] in-process | 12 | Always-visible meter with peak hold |
| 20 | Waterfall cursor (passband overlay) | P1 | @developer | [~] in-process | 13, 6 | Mode-aware passband highlight |

| 21 | Waterfall cursor drag-to-tune | P1 | @developer | [ ] pending | 20 | Dragging cursor changes frequency |
| 22 | Client-side DSP: volume + squelch nodes | P0 | @developer | [~] in-process | -- | Web Audio API gain + gate in AudioManager |
| 23 | Client-side DSP: bandpass + notch filters | P1 | @developer | [x] complete | 22 | BiquadFilterNode chain |
| 24 | Client-side DSP: noise reduction worklet | P2 | @developer | [~] in-process | 22 | Spectral subtraction AudioWorklet |
| 25 | Client-side DSP: compressor + 3-band EQ | P1 | @developer | [x] complete | 22 | DynamicsCompressorNode + 3x BiquadFilter |
| 26 | DSP controls panel component | P1 | @developer | [~] in-process | 23, 25 | UI for all DSP parameters |
| 27 | TX visualization switching | P1 | @developer | [~] in-process | 12, 22 | Show TX audio in active viz during PTT |
| 28 | VOX mode with hot-mic prevention | P1 | @developer | [~] in-process | 22 | Audio gate threshold + hang timer |
| 29 | Region-aware BandSelector component | P1 | @developer | [~] in-process | 1, 3 | All region bands; greyed for non-enabled |
| 30 | Frequency presets UI | P1 | @developer | [~] in-process | 7, 29 | Preset selector + label in freq display |
| 31 | Layout system: schema + persistence | P1 | @developer | [x] complete | 18 | JSON layout configs in localStorage |
| 32 | Layout system: save/load/export/import UI | P1 | @developer | [ ] pending | 31 | Layout management panel |
| 33 | Main page layout refactor for configurable panels | P1 | @developer | [x] complete | 31 | Dynamic grid from layout config |
| 34 | Virtual device passthrough documentation | P2 | @developer | [~] in-process | -- | Docs + helper scripts |
| 35 | Extended CAT frontend controls (VFO, SWR, CTCSS) | P1 | @developer | [x] complete | 5, 10 | UI for new CAT features |
| 36 | ModeSelector curated mode support | P1 | @developer | [x] complete | 6, 3 | Filter modes per radio capability |
| 37 | Backend tests: band plan, presets, config schema | P0 | @tester | [ ] pending | 1, 2, 7 | pytest for new backend features |
| 38 | Backend tests: extended CAT, simulation type | P1 | @tester | [ ] pending | 4, 5 | pytest for new CAT + simulation |
| 39 | Frontend build verification | P1 | @tester | [ ] pending | 33 | npm run build passes clean |
| 40 | Full lint + type check pass | P0 | @tester | [ ] pending | 33 | ruff, mypy, svelte-check all clean |

---

## Parallelization Strategy

### Wave 1 -- Foundation (no interdependencies within wave)
Tasks 1, 2, 9, 12, 22, 34

These are all independent foundations: band plan data, config schema changes, theme CSS system, visualization renderer interface, DSP audio node infrastructure, and passthrough docs. All can proceed in parallel.

### Wave 2 -- Core Features (depend on Wave 1)
Tasks 3, 4, 10, 11, 13, 14, 15, 23, 25

Config frontend types (needs 2), explicit simulation (needs 2), accessibility (needs 9), scroll-wheel (needs 10 -- sequential within wave), waterfall refactor + spectrum + oscilloscope (need 12), DSP filters + EQ (need 22). Tasks 3/4 are sequential. Tasks 10/11 are sequential. Others parallelize freely.

### Wave 3 -- Integrated Features (depend on Wave 2)
Tasks 5, 6, 7, 8, 16, 17, 18, 19, 20, 24, 26, 27, 28, 29, 30, 41

Extended CAT, curated modes, presets API, band plan API, remaining renderers (constellation, phase, 3D spectrogram), viz switcher, LUFS meter, cursor, NR worklet, DSP panel, TX viz, VOX, band selector, preset UI. Many of these parallelize (e.g., 5/6/7/8 are backend; 16/17/18/19/41 are frontend viz; 26/28 are frontend DSP).

### Wave 4 -- Layout + Integration (depend on Wave 3)
Tasks 31, 33, 35, 36

Layout system, main page refactor, extended CAT UI, curated mode UI. Tasks 35/36 parallelize with 31/33.

### Wave 5 -- Polish + Finalization
Tasks 32, 21, 37, 38, 39, 40

Layout export/import UI, drag-to-tune cursor, all test suites, final lint/type checks.

---

## Task Descriptions

### Task 1: Region-aware band plan data module

**Files**: `server/bandplan.py` (new), `ui/src/lib/bandplan.ts` (new)

Create a pure-data module defining amateur band plans for known regions (us, eu, au). Each band entry contains: `name` (e.g. "20m"), `lower_mhz`, `upper_mhz`, `default_mode`. Include all HF bands (160m through 10m), VHF (6m, 2m), and UHF (70cm).

Backend (`server/bandplan.py`):
- `BAND_PLANS: dict[str, list[BandDef]]` keyed by region code
- `BandDef` is a Pydantic `BaseModel` with fields: `name: str`, `lower_mhz: float`, `upper_mhz: float`, `default_mode: str`
- `get_bands(region: str) -> list[BandDef]` returns the band list for a region; raises `ValueError` for unknown regions
- US band plan includes: 160m (1.8-2.0), 80m (3.5-4.0), 60m (5.3305-5.4065), 40m (7.0-7.3), 30m (10.1-10.15), 20m (14.0-14.35), 17m (18.068-18.168), 15m (21.0-21.45), 12m (24.89-24.99), 10m (28.0-29.7), 6m (50.0-54.0), 2m (144.0-148.0), 70cm (420.0-450.0)
- EU and AU plans differ in band edges per their regulatory domains

Frontend (`ui/src/lib/bandplan.ts`):
- Mirror the same data as TypeScript constants: `BandDef` interface, `BAND_PLANS` record
- Export `getBands(region: string): BandDef[]`

**Done when**: Both files exist, data is consistent between backend and frontend, `uv run mypy .` passes for bandplan.py, `npm run build` compiles bandplan.ts without errors.

---

### Task 2: Config schema -- operator.region, radio.type, radio.bands, presets

**File**: `server/config.py`

Extend the Pydantic config models:

1. Add `region: str = "us"` to `OperatorConfig`. Add a `@field_validator` that checks `region` is in `BAND_PLANS.keys()` (import from `bandplan.py`).

2. Add `type: Literal["real", "simulated"] = "real"` to `RadioConfig`.

3. Add `bands: list[str] = []` to `RadioConfig`. An empty list means "all bands in region" (resolved at runtime, not stored).

4. Add a new `PresetConfig(BaseModel)` with fields: `id: str`, `name: str`, `band: str`, `frequency_mhz: float`, `offset_mhz: float = 0.0`, `ctcss_tone: float | None = None`, `mode: str | None = None`.

5. Add `presets: list[PresetConfig] = []` to `RigletConfig`.

6. Add a `@model_validator` on `RigletConfig` that validates each radio's `bands` list entries exist in the band plan for `self.operator.region`.

7. Add a `@model_validator` on `RigletConfig` that validates each preset's `band` exists in the band plan.

8. For `type: "simulated"` radios, relax the `audio_fields_required_when_enabled` validator -- simulated radios do not need real audio devices.

9. Update `default_config()` to include `region="us"` in the operator section.

**Done when**: `uv run pytest` passes, `uv run mypy .` passes, config round-trips (load -> save -> load) with new fields, invalid region/band values are rejected with clear errors.

---

### Task 3: Config schema frontend types

**File**: `ui/src/lib/types.ts`

Update TypeScript interfaces to match the new config schema:

1. Add `region: string` to the operator section of `RigletConfig`.
2. Add `type: 'real' | 'simulated'` and `bands: string[]` to `RadioConfig`.
3. Add `PresetConfig` interface: `id: string`, `name: string`, `band: string`, `frequency_mhz: number`, `offset_mhz: number`, `ctcss_tone: number | null`, `mode: string | null`.
4. Add `presets: PresetConfig[]` to `RigletConfig`.

**Done when**: `npm run build` compiles without type errors.

---

### Task 4: Explicit simulation radio type

**Files**: `server/state.py`, `server/main.py`

Refactor `RadioInstance` and `RadioManager` so that simulation is driven by `RadioConfig.type` rather than connection failure:

1. In `RadioInstance.__init__`, set `self.simulation = (config.type == "simulated")` immediately.
2. In `RadioManager.startup()`:
   - If `radio_cfg.type == "simulated"`: set `simulation=True`, `online=True`, skip `connect_rigctld()`.
   - If `radio_cfg.type == "real"` and `radio_cfg.enabled`: call `connect_rigctld()`. On failure, set `online=False`, `simulation=False` (error state, NOT silent simulation).
   - If `radio_cfg.type == "real"` and not `radio_cfg.enabled`: set `online=False`, `simulation=False`.
3. In `connect_rigctld()`: on connection failure, do NOT set `simulation=True`. Set `online=False` only. Log as error, not warning.
4. In `_poll_loop()`: if `not self.online and not self.simulation`, attempt reconnect (existing behavior). If `self.simulation`, run simulated polling (existing behavior). If `not self.online and self.config.type == "real"`, do NOT generate fake data.
5. Update `RadioManager.status()` to include `type` field in the status dict.

**Done when**: `uv run pytest` passes, `uv run mypy .` passes. A `type: simulated` radio starts online with fake data. A `type: real` radio with unreachable rigctld shows as offline (not simulated).

---

### Task 5: Extended CAT -- VFO, SWR, CTCSS

**Files**: `server/state.py`, `server/routers/cat.py`

Add new rigctld commands to `RadioInstance`:

1. `get_vfo() -> str`: query current VFO (`+\get_vfo`). Returns "VFOA", "VFOB", etc. Simulation returns "VFOA".
2. `set_vfo(vfo: str) -> None`: set active VFO (`+\set_vfo {vfo}`). Simulation stores value.
3. `get_swr() -> float`: query SWR meter (`+\get_level SWR`). Returns float (e.g. 1.5). Simulation returns 1.0.
4. `get_ctcss() -> float`: query CTCSS tone (`+\get_ctcss_tone`). Returns Hz (e.g. 88.5). Simulation returns 0.0.
5. `set_ctcss(tone: float) -> None`: set CTCSS tone (`+\set_ctcss_tone {tone_hz}`). 0 disables. Simulation stores value.

Add state fields to `RadioInstance`: `vfo: str = "VFOA"`, `swr: float = 1.0`, `ctcss_tone: float = 0.0`.

Update `poll_once()` to also query VFO and SWR (when PTT active) and include changes in the pushed state.

Add REST endpoints in `cat.py`:
- `POST /radio/{radio_id}/cat/vfo` with body `{"vfo": "VFOB"}`
- `GET /radio/{radio_id}/cat/swr` returns `{"swr": 1.5}`
- `POST /radio/{radio_id}/cat/ctcss` with body `{"tone": 88.5}`

Add WebSocket message types in `ws_control`: `vfo`, `ctcss`.

**Done when**: All new endpoints return correct data in simulation mode. `uv run pytest` and `uv run mypy .` pass.

---

### Task 6: Curated mode list per radio

**Files**: `server/modes.py` (new), `server/routers/cat.py`

Create a module mapping Hamlib model numbers to supported mode lists:

1. `HAMLIB_MODES: dict[int, list[str]]` -- maps model number to ordered list of supported modes. Include entries for common radios: IC-706mkiig (model 3009), FT-991A (model 36017), TS-590 (model 2029). Unknown models return a generic list: `["USB", "LSB", "CW", "CWR", "AM", "FM", "RTTY", "RTTYR", "PKTUSB", "PKTLSB"]`.
2. `get_modes(hamlib_model: int) -> list[str]` -- returns the mode list for a model, falling back to generic.
3. Add `GET /api/radio/{radio_id}/modes` endpoint in `cat.py` that returns `{"modes": [...]}` using the radio's `hamlib_model`.

**Done when**: Endpoint returns correct mode list for known models and generic list for unknown. `uv run pytest` and `uv run mypy .` pass.

---

### Task 7: Frequency presets API

**Files**: `server/routers/system.py`

Add REST endpoints for preset management:

1. `GET /api/presets` -- returns `{"presets": [...]}` from current config.
2. `POST /api/presets` -- body is a single `PresetConfig`. Appends to config, saves, returns updated list.
3. `PUT /api/presets/{preset_id}` -- updates an existing preset by ID. 404 if not found.
4. `DELETE /api/presets/{preset_id}` -- removes a preset by ID. 404 if not found.
5. `POST /api/presets/import` -- body is `{"presets": [...]}`. Replaces all presets. Returns updated list.
6. `GET /api/presets/export` -- returns `{"presets": [...]}` (same as GET but semantically for file download).

All mutations call `save_config()` after modifying the in-memory config. Validate preset band against current region's band plan.

Update `ui/src/lib/api.ts` with typed functions: `getPresets()`, `createPreset()`, `updatePreset()`, `deletePreset()`, `importPresets()`, `exportPresets()`.

**Done when**: All endpoints work, round-trip import/export preserves data, invalid band names are rejected. `uv run pytest` and `uv run mypy .` pass.

---

### Task 8: Band plan API endpoint

**Files**: `server/routers/system.py`

Add `GET /api/bandplan` endpoint:
- Returns `{"region": "us", "bands": [...]}` where bands is the list of `BandDef` objects for the current config's `operator.region`.
- Uses `bandplan.get_bands()` from task 1.

Add `getBandPlan()` to `ui/src/lib/api.ts`.

**Done when**: Endpoint returns correct band data for the configured region. `uv run pytest` and `uv run mypy .` pass.

---

### Task 9: Theme infrastructure (CSS custom properties)

**Files**: `ui/src/app.css` (new or extend existing global styles), `ui/src/lib/stores.ts`, `ui/src/lib/theme.ts` (new)

Create a theming system using CSS custom properties:

1. Define a `ThemeMode` type: `'light' | 'dark' | 'system'`.
2. Create `ui/src/lib/theme.ts` with:
   - `initTheme()`: reads preference from `localStorage` key `riglet-theme`, falls back to `prefers-color-scheme` media query. Sets `data-theme` attribute on `<html>`.
   - `setTheme(mode: ThemeMode)`: persists to localStorage, updates `data-theme` attribute.
   - `getTheme(): ThemeMode`: reads current setting.
3. Define CSS custom properties in `ui/src/app.css` under `[data-theme="dark"]` (default) and `[data-theme="light"]` selectors. Properties include:
   - `--bg-primary`, `--bg-secondary`, `--bg-surface`, `--bg-elevated`
   - `--text-primary`, `--text-secondary`, `--text-muted`
   - `--border-primary`, `--border-subtle`
   - `--accent`, `--accent-hover`
   - `--online-color`, `--offline-color`, `--ptt-color`
   - `--waterfall-bg`
4. Add a `theme` writable store to `stores.ts`.
5. Do NOT yet migrate existing components to use these properties (that happens incrementally as each component is touched in later tasks). But ensure the properties are loaded at app startup.

**Done when**: `initTheme()` correctly detects system preference, `setTheme('light')` switches all CSS variables, `npm run build` passes.

---

### Task 10: Accessibility foundation

**Files**: Multiple component files in `ui/src/lib/components/`, `ui/src/routes/+page.svelte`

Add accessibility infrastructure across all existing components:

1. Add `role`, `aria-label`, `aria-live`, `aria-pressed` (for PTT), `aria-valuenow`/`aria-valuemin`/`aria-valuemax` (for sliders/meters) to all interactive elements.
2. Add `tabindex` and keyboard event handlers (`on:keydown`) to all controls that currently only respond to click/mouse.
3. Add a skip-to-content link at the top of `+page.svelte`.
4. Ensure all color contrast ratios meet WCAG 2.1 AA in both themes (check against the CSS properties from task 9).
5. Add `@media (prefers-reduced-motion: reduce)` rules to disable waterfall scrolling animation and meter transitions.
6. `FrequencyDisplay`: arrow keys nudge frequency, Enter confirms.
7. `BandSelector`: arrow keys navigate between bands, Enter/Space selects.
8. `ModeSelector`: arrow keys navigate, Enter/Space selects.
9. `PttButton`: Space/Enter toggles PTT. `aria-pressed` reflects state.
10. `AudioControls` sliders: arrow keys adjust, Home/End for min/max.

**Done when**: All interactive elements are keyboard-reachable via Tab. Screen reader (VoiceOver) announces frequency, mode, PTT state, S-meter reading. `npm run build` passes.

---

### Task 11: Scroll-wheel mixin for dial controls

**Files**: `ui/src/lib/actions/scrollwheel.ts` (new)

Create a Svelte action (use directive) for scroll-wheel interaction:

1. `scrollWheel(node: HTMLElement, params: { onDelta: (delta: number) => void, step?: number })`: attaches a `wheel` event listener to the element.
2. On `wheel` event, call `event.preventDefault()` (only when pointer is over the element) and invoke `onDelta(delta)` with +1 or -1 based on scroll direction.
3. Apply to: `FrequencyDisplay` (scroll nudges freq by configurable step), `AudioControls` volume/gain sliders, and future dial controls.
4. Respect `pointer-events` -- only capture when the element is hovered (use `pointerenter`/`pointerleave` to gate).

**Done when**: Scroll-wheel on FrequencyDisplay changes frequency. Scroll-wheel on volume slider changes volume. Scrolling elsewhere on the page does NOT get hijacked. `npm run build` passes.

---

### Task 12: Visualization renderer interface

**Files**: `ui/src/lib/viz/types.ts` (new), `ui/src/lib/viz/base-renderer.ts` (new)

Define the pluggable visualization architecture:

1. `VisualizationMode` type: `'waterfall' | 'spectrum' | 'oscilloscope' | 'constellation' | 'phase' | 'spectrogram3d'`
2. `RendererContext` interface: `{ canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D, width: number, height: number, centerMhz: number, spanKhz: number, mode: string }`
3. `Renderer` interface:
   - `init(context: RendererContext): void` -- called once on mount
   - `render(data: VisualizationData): void` -- called per frame
   - `resize(width: number, height: number): void`
   - `destroy(): void` -- cleanup
4. `VisualizationData` interface: `{ fftBins: number[] | null, pcmSamples: Float32Array | null, sampleRate: number, timestamp: number }`
5. `RendererRegistry`: a `Map<VisualizationMode, () => Renderer>` factory registry. Export `registerRenderer()` and `createRenderer()`.

**Done when**: All interfaces and types compile. Registry can store and retrieve renderer factories. `npm run build` passes.

---

### Task 13: Refactor Waterfall to use renderer interface

**Files**: `ui/src/lib/viz/waterfall-renderer.ts` (new), `ui/src/lib/components/Waterfall.svelte`, `ui/src/lib/components/VisualizationPanel.svelte` (new)

1. Extract the rendering logic from `Waterfall.svelte` into `waterfall-renderer.ts` implementing the `Renderer` interface from task 12.
   - `init()`: allocate ImageData, set up color map.
   - `render()`: scroll-and-draw logic (currently in `scrollAndDraw()`).
   - `resize()`: reallocate ImageData.
   - `destroy()`: cleanup.

2. Create `VisualizationPanel.svelte` -- a generic container component that:
   - Accepts a `mode: VisualizationMode` prop and a `radioId: string` prop.
   - Manages the canvas element and `ResizeObserver`.
   - Connects to the waterfall WebSocket for FFT data.
   - Instantiates the correct renderer from the registry.
   - Calls `renderer.render()` on each data frame.
   - Supports switching renderers at runtime (destroy old, init new).

3. Update `+page.svelte` to use `VisualizationPanel` instead of `Waterfall` directly.

4. Register `waterfall-renderer` in the `RendererRegistry`.

**Done when**: Waterfall displays identically to before. The old `Waterfall.svelte` can be deleted or is now a thin wrapper. `npm run build` passes. No visual regression.

---

### Task 14: Spectrum scope renderer

**Files**: `ui/src/lib/viz/spectrum-renderer.ts` (new)

Implement a spectrum scope (frequency vs. amplitude) renderer:

1. Implements `Renderer` interface.
2. `render()`: draws FFT bins as a filled line graph. X-axis = frequency (left to right), Y-axis = amplitude (bottom to top).
3. Color: green line on dark background (respect theme CSS variables).
4. Optional peak-hold trace: a second line (in dimmer color) that decays slowly, showing recent maximum values per bin.
5. Frequency axis labels along the bottom (reuse center/span from RendererContext).
6. Amplitude axis labels along the left (-120 dB to 0 dB range, adjustable).
7. Register in `RendererRegistry` under key `'spectrum'`.

**Done when**: Spectrum scope renders real-time FFT data. Peak hold trace visible and decaying. `npm run build` passes.

---

### Task 15: Oscilloscope renderer

**Files**: `ui/src/lib/viz/oscilloscope-renderer.ts` (new)

Implement a time-domain waveform renderer:

1. Implements `Renderer` interface.
2. `render()`: draws PCM samples as a continuous waveform. X-axis = time, Y-axis = amplitude (-1 to +1).
3. Trigger: simple zero-crossing trigger to stabilize the display.
4. Color: green trace on dark background (theme-aware).
5. Graticule: horizontal center line, vertical time divisions.
6. Register in `RendererRegistry` under key `'oscilloscope'`.

Note: This renderer uses `VisualizationData.pcmSamples` rather than `fftBins`. The `VisualizationPanel` must also provide raw PCM data from the audio WebSocket to renderers that need it.

**Done when**: Oscilloscope renders time-domain audio waveform with stable triggering. `npm run build` passes.

---

### Task 16: Constellation renderer

**Files**: `ui/src/lib/viz/constellation-renderer.ts` (new)

Implement a constellation / goniometer (X-Y plot) renderer:

1. Implements `Renderer` interface.
2. `render()`: plots successive PCM sample pairs as (x, y) dots on a circular display. For mono audio, use sample[n] vs sample[n+1] (phase space plot).
3. Dot persistence: dots fade over time (trail effect) using alpha blending on the canvas.
4. Graticule: crosshair at center, circular boundary.
5. Register in `RendererRegistry` under key `'constellation'`.

**Done when**: Constellation displays phase-space plot of audio signal. `npm run build` passes.

---

### Task 17: Phase/correlation meter renderer

**Files**: `ui/src/lib/viz/phase-renderer.ts` (new)

Implement a phase correlation meter:

1. Implements `Renderer` interface.
2. `render()`: computes autocorrelation of the PCM signal and displays as a horizontal bar meter ranging from -1 (out of phase) through 0 (uncorrelated) to +1 (in phase).
3. Needle or filled bar indicator with color coding: green (+1 region), yellow (0 region), red (-1 region).
4. Register in `RendererRegistry` under key `'phase'`.

**Done when**: Phase meter renders and responds to audio signal characteristics. `npm run build` passes.

---

### Task 18: Visualization mode switcher UI

**Files**: `ui/src/lib/components/VizSwitcher.svelte` (new), `ui/src/lib/components/VisualizationPanel.svelte`

Create a mode-switching control for the visualization area:

1. `VizSwitcher.svelte`: a row of icon/label buttons for each available `VisualizationMode`. Highlights the active mode. Emits a `select` event with the chosen mode.
2. Integrate into `VisualizationPanel.svelte`: place the switcher above or overlapping the top of the canvas area.
3. When the user selects a new mode, `VisualizationPanel` destroys the current renderer and instantiates the new one.
4. Keyboard accessible: arrow keys navigate modes, Enter/Space selects.
5. The spectrum scope can optionally overlay any other visualization (toggled by a separate checkbox/button). When overlaid, both renderers draw to the same canvas in sequence.

**Done when**: User can switch between waterfall, spectrum, oscilloscope, constellation, and phase meter. Transitions are smooth (no flash/glitch). `npm run build` passes.

---

### Task 19: LUFS audio meter component

**Files**: `ui/src/lib/components/LufsMeter.svelte` (new), `ui/src/lib/audio/lufs.ts` (new)

Create an always-visible audio loudness meter:

1. `lufs.ts`: implement LUFS (Loudness Units Full Scale) measurement per ITU-R BS.1770:
   - K-weighting filter (two biquad stages).
   - Momentary loudness (400ms window).
   - Short-term loudness (3s window).
   - Integrated loudness (entire measurement period).
   - Accept Float32Array PCM input, return LUFS value.
2. `LufsMeter.svelte`:
   - Vertical bar meter with color gradient: green (quiet) -> yellow (moderate) -> red (loud).
   - Peak-hold indicator: a horizontal line that marks the maximum level and decays slowly (e.g., 3 dB/sec fall rate, or holds for 2 seconds then drops).
   - Numeric LUFS readout below the bar.
   - Displayed alongside the visualization area (not inside it).
   - Receives PCM data from the audio pipeline (passed as prop or via store).
3. Integrate into `+page.svelte` layout: position to the right of the visualization panel or as a narrow vertical strip.

**Done when**: LUFS meter updates in real time from RX audio. Peak hold shows and decays. Meter is always visible. `npm run build` passes.

---

### Task 20: Waterfall cursor (passband overlay)

**Files**: `ui/src/lib/viz/waterfall-renderer.ts`, `ui/src/lib/viz/cursor.ts` (new)

Add a passband cursor overlay to the waterfall:

1. `cursor.ts`: `PassbandCursor` class that:
   - Accepts: `centerFreqMhz`, `cursorFreqMhz`, `mode`, `spanKhz`, `canvasWidth`.
   - Computes passband width based on mode: USB/LSB = 2.4 kHz, CW = 0.5 kHz, AM = 6 kHz, FM = 12 kHz, RTTY = 0.5 kHz. Mode-to-bandwidth map is configurable.
   - Computes pixel positions for the passband region.
   - For SSB: passband extends from carrier on one side only (USB = above, LSB = below).
   - For AM/FM: passband is centered.
   - Returns `{ leftPx: number, rightPx: number, centerPx: number }`.
2. In `waterfall-renderer.ts`, after drawing the waterfall, draw the cursor overlay:
   - Semi-transparent highlight over the passband region.
   - Dim the area outside the passband.
   - Draw a thin vertical line at the cursor center/edge.
3. The cursor position reflects the current tuned frequency relative to the waterfall center.

**Done when**: Passband overlay is visible on the waterfall, adapts to mode changes, and tracks frequency. `npm run build` passes.

---

### Task 21: Waterfall cursor drag-to-tune

**Files**: `ui/src/lib/viz/cursor.ts`, `ui/src/lib/components/VisualizationPanel.svelte`

Make the waterfall cursor draggable to change frequency:

1. Add mouse event handlers to the canvas in `VisualizationPanel`:
   - `mousedown` on the passband region starts a drag.
   - `mousemove` during drag updates the cursor position and computes the new frequency from pixel offset.
   - `mouseup` ends the drag and sends the frequency change via the control WebSocket.
2. Cursor changes to `grab` / `grabbing` during interaction.
3. Also support click-to-tune: clicking anywhere on the waterfall tunes to that frequency.
4. Touch support: same behavior with `touchstart` / `touchmove` / `touchend`.
5. Scroll-wheel on the waterfall: zoom the span (narrow/widen the visible bandwidth). Use the scroll-wheel action from task 11.

**Done when**: Dragging the cursor changes the radio frequency. Click-to-tune works. Touch works. `npm run build` passes.

---

### Task 22: Client-side DSP -- volume + squelch nodes

**Files**: `ui/src/lib/audio/audio-manager.ts`, `ui/src/lib/audio/squelch-worklet.js` (new)

Extend `AudioManager` with volume and squelch processing:

1. **Volume**: Already exists as a `GainNode`. Ensure it is exposed with `getVolume()` and `setVolume(v: number)` (0.0 to 1.0). No change needed here beyond verification.

2. **Squelch**: Create `squelch-worklet.js` AudioWorkletProcessor:
   - Parameters: `threshold` (dBFS, default -80), `holdMs` (default 300).
   - Logic: compute RMS of each 128-sample block. If RMS < threshold, gate output to zero. Hold open for `holdMs` after last above-threshold block.
   - Register as `'squelch-processor'`.
3. In `AudioManager`:
   - Add `squelchNode: AudioWorkletNode` in the RX chain between the existing worklet and the gain node.
   - Add `setSquelch(thresholdDb: number)` method that sets the parameter.
   - Add `squelchEnabled: boolean` with `enableSquelch()` / `disableSquelch()` to bypass the node.
4. Audio chain order: PCM worklet -> squelch -> gain -> destination.

**Done when**: Setting squelch threshold gates quiet audio. Volume control still works. `npm run build` passes.

---

### Task 23: Client-side DSP -- bandpass + notch filters

**Files**: `ui/src/lib/audio/audio-manager.ts`, `ui/src/lib/audio/dsp-chain.ts` (new)

Add configurable filter nodes:

1. Create `dsp-chain.ts` -- a `DspChain` class managing the ordered sequence of AudioNodes:
   - `bandpassNode: BiquadFilterNode` (type `'bandpass'`, configurable center freq + Q).
   - `notchNode: BiquadFilterNode` (type `'notch'`, configurable center freq + Q).
   - Methods: `setBandpass(centerHz: number, widthHz: number)`, `setNotch(centerHz: number, widthHz: number)`, `enableBandpass(enabled: boolean)`, `enableNotch(enabled: boolean)`.
   - Chain is inserted into the AudioManager RX path.
2. Integrate `DspChain` into `AudioManager`:
   - Chain order: PCM worklet -> bandpass -> notch -> squelch -> gain -> destination.
   - Each node can be bypassed (disconnected from chain, reconnect neighbors).
3. Default state: all filters bypassed.

**Done when**: Bandpass filter audibly filters audio when enabled. Notch filter removes a specific tone. Bypassing restores full audio. `npm run build` passes.

---

### Task 24: Client-side DSP -- noise reduction worklet

**Files**: `ui/src/lib/audio/nr-worklet.js` (new), `ui/src/lib/audio/dsp-chain.ts`

Implement spectral subtraction noise reduction:

1. `nr-worklet.js` AudioWorkletProcessor:
   - Parameters: `amount` (0.0 to 1.0, default 0.5).
   - Algorithm: collect 256-sample frames, FFT (use a simple DFT or precomputed twiddle factors since AudioWorklet cannot import numpy), estimate noise floor from quiet periods, subtract scaled noise spectrum, IFFT, overlap-add.
   - Simpler alternative if FFT is too complex for worklet: use a Wiener filter approximation with exponential moving average of noise spectrum.
   - Register as `'nr-processor'`.
2. Add `nrNode: AudioWorkletNode` to `DspChain`.
3. Chain order: PCM worklet -> bandpass -> notch -> NR -> squelch -> gain -> destination.
4. Methods: `setNrAmount(amount: number)`, `enableNr(enabled: boolean)`.

**Done when**: Noise reduction audibly reduces background noise. Amount parameter controls aggressiveness. `npm run build` passes.

---

### Task 25: Client-side DSP -- compressor + 3-band EQ

**Files**: `ui/src/lib/audio/dsp-chain.ts`

Add dynamics and EQ processing:

1. **Compressor** (for TX path): `DynamicsCompressorNode` with configurable threshold, ratio, attack, release.
   - Methods: `setCompressor(threshold: number, ratio: number)`, `enableCompressor(enabled: boolean)`.
   - Insert into TX audio chain in `AudioManager`: mic source -> compressor -> PCM worklet.

2. **3-band EQ** (for RX path): three `BiquadFilterNode` instances:
   - Low shelf: 300 Hz, configurable gain (-12 to +12 dB).
   - Peaking: 1000 Hz, configurable gain.
   - High shelf: 3000 Hz, configurable gain.
   - Methods: `setEqBand(band: 'low' | 'mid' | 'high', gainDb: number)`, `enableEq(enabled: boolean)`.
   - Insert into RX chain: ... -> NR -> EQ -> squelch -> gain -> destination.

3. Chain order (final RX): PCM worklet -> bandpass -> notch -> NR -> EQ low -> EQ mid -> EQ high -> squelch -> gain -> destination.
4. Chain order (final TX): mic source -> compressor -> PCM worklet (TX capture).

**Done when**: Compressor affects TX audio dynamics. EQ audibly changes tone of RX audio. All can be bypassed. `npm run build` passes.

---

### Task 26: DSP controls panel component

**Files**: `ui/src/lib/components/DspPanel.svelte` (new)

Create a UI panel for all DSP parameters:

1. Sections: Filters (bandpass center/width, notch center/width), Noise Reduction (amount slider), EQ (3 band sliders), Compressor (threshold/ratio).
2. Each section has an enable/disable toggle.
3. All sliders use `<input type="range">` with ARIA labels and keyboard support.
4. Apply the scroll-wheel action from task 11 to all sliders.
5. Collapsible panel (click header to expand/collapse).
6. Changes apply in real time by calling `DspChain` methods.
7. Integrate into the controls column in `+page.svelte`.

**Done when**: All DSP parameters are adjustable via the panel. Toggling sections enables/disables the corresponding audio nodes. `npm run build` passes.

---

### Task 27: TX visualization switching

**Files**: `ui/src/lib/components/VisualizationPanel.svelte`, `ui/src/lib/audio/audio-manager.ts`

Show transmitted audio in the visualization during PTT:

1. In `AudioManager`, expose TX audio data (PCM samples from the microphone) via a callback or store, similar to how RX data feeds the visualization.
2. In `VisualizationPanel`, when PTT is active:
   - Switch the data source from RX audio/FFT to TX audio.
   - The active renderer continues to render but with TX data.
   - Add a visual indicator ("TX" badge) on the visualization area.
3. When PTT is released, switch back to RX data.
4. For the waterfall renderer specifically, run a client-side FFT on the TX PCM to generate FFT bins (since the server only sends RX FFT).

**Done when**: During PTT, the visualization shows the operator's transmitted audio. Visual TX indicator is present. Switching is seamless. `npm run build` passes.

---

### Task 28: VOX mode with hot-mic prevention

**Files**: `ui/src/lib/audio/vox.ts` (new), `ui/src/lib/audio/audio-manager.ts`, `ui/src/lib/components/PttButton.svelte`

Implement voice-activated transmit:

1. `vox.ts`: `VoxDetector` class:
   - Constructor params: `thresholdDb: number` (default -30), `hangTimeMs: number` (default 500), `antiVoxDelayMs: number` (default 100).
   - Method `process(pcmSamples: Float32Array): boolean` -- returns true if voice detected (above threshold, or within hang time).
   - Anti-VOX: ignore mic input briefly after RX audio plays (prevents feedback loop from triggering PTT).
   - Hot-mic prevention: require the level to exceed threshold for at least `antiVoxDelayMs` before triggering (prevents transient noise from keying up).
2. In `AudioManager`:
   - Add `VoxDetector` instance.
   - When VOX is enabled, monitor TX audio in the PCM worklet's `tx` messages. If `VoxDetector.process()` returns true, send PTT on via control WebSocket. When it returns false (hang time expired), send PTT off.
3. In `PttButton.svelte`:
   - Add VOX mode toggle button.
   - When VOX active, show "VOX" label and a visual indicator of mic activity.
   - Manual PTT button still works alongside VOX.
4. VOX is disabled by default.

**Done when**: VOX mode correctly keys PTT on voice. Hot-mic prevention works (brief noise does not trigger). Hang time works. Manual PTT overrides. `npm run build` passes.

---

### Task 29: Region-aware BandSelector component

**Files**: `ui/src/lib/components/BandSelector.svelte`

Refactor the BandSelector to be region-aware:

1. Accept new props: `region: string`, `enabledBands: string[]` (from radio config).
2. Fetch band list from `bandplan.ts` (task 1) for the given region.
3. Render a pill for every band in the region (not just HF).
4. Bands in `enabledBands` are interactive and fully styled.
5. Bands NOT in `enabledBands` are greyed out, non-interactive, with a tooltip "Not enabled for this radio".
6. Active band (matching current frequency) is highlighted.
7. Include VHF/UHF bands (6m, 2m, 70cm) when present in the region.
8. Keyboard navigable (arrow keys between pills).

**Done when**: All region bands shown. Non-enabled bands are visually distinct and non-clickable. Active band highlights correctly. `npm run build` passes.

---

### Task 30: Frequency presets UI

**Files**: `ui/src/lib/components/PresetSelector.svelte` (new), `ui/src/lib/components/FrequencyDisplay.svelte`

Create UI for frequency presets:

1. `PresetSelector.svelte`:
   - Dropdown or pill list of presets, grouped by band.
   - Selecting a preset sends frequency (and optionally mode/CTCSS) to the radio via control WebSocket.
   - "Add preset" button: saves current frequency/mode as a new preset (opens a name input).
   - "Manage presets" opens a modal for edit/delete/import/export.
   - Import: file picker for JSON. Export: triggers JSON file download.
2. In `FrequencyDisplay.svelte`:
   - When the current frequency matches a preset, show the preset name as a small label below or beside the frequency readout.
   - Match tolerance: within 1 kHz of preset frequency.
3. Integrate `PresetSelector` into the radio header area in `+page.svelte`.

**Done when**: Presets can be created, selected, edited, deleted, imported, and exported via the UI. Active preset label shows in frequency display. `npm run build` passes.

---

### Task 31: Layout system -- schema + persistence

**Files**: `ui/src/lib/layout/types.ts` (new), `ui/src/lib/layout/store.ts` (new), `ui/src/lib/layout/defaults.ts` (new)

Define the layout configuration system:

1. `types.ts`:
   - `LayoutPanel` interface: `{ id: string, component: string, position: { row: number, col: number, rowSpan: number, colSpan: number } }`.
   - `LayoutConfig` interface: `{ id: string, name: string, columns: number, rows: number, panels: LayoutPanel[] }`.
   - `component` values: `'visualization'`, `'frequency'`, `'band-selector'`, `'mode-selector'`, `'ptt'`, `'smeter'`, `'audio'`, `'dsp'`, `'lufs-meter'`, `'presets'`, `'vfo'`, `'cat-extended'`.
2. `defaults.ts`:
   - `DEFAULT_LAYOUTS: LayoutConfig[]` with at least three presets: "Voice Operating" (emphasizes waterfall + PTT), "Digital Modes" (smaller waterfall, more controls), "SWL" (large waterfall, no TX controls).
3. `store.ts`:
   - Svelte writable store for current `LayoutConfig`.
   - `loadLayout(id: string)`: load from localStorage key `riglet-layout-{id}`.
   - `saveLayout(layout: LayoutConfig)`: persist to localStorage.
   - `listLayouts(): { id: string, name: string, isDefault: boolean }[]`: list all available (default + custom).
   - `exportLayout(layout: LayoutConfig): string`: serialize to JSON string.
   - `importLayout(json: string): LayoutConfig`: parse and validate.
   - `deleteLayout(id: string)`: remove from localStorage (cannot delete defaults).

**Done when**: Layout configs can be created, saved, loaded, exported, and imported. Default layouts exist. `npm run build` passes.

---

### Task 32: Layout system -- save/load/export/import UI

**Files**: `ui/src/lib/components/LayoutManager.svelte` (new)

Create the layout management UI:

1. A toolbar button (gear icon or layout icon) in the topbar opens a dropdown/panel.
2. List of available layouts (defaults + custom) with select, rename, delete actions.
3. "Save current" button to save the active layout.
4. "Save as new" button to clone the current layout with a new name.
5. "Export" button: downloads the layout as a `.json` file.
6. "Import" button: file picker to load a `.json` layout file.
7. Confirmation dialog before deleting custom layouts.
8. Integrate into the topbar in `+page.svelte`.

**Done when**: Full layout management CRUD works through the UI. Import/export produces valid JSON files. `npm run build` passes.

---

### Task 33: Main page layout refactor for configurable panels

**Files**: `ui/src/routes/+page.svelte`

Refactor the main page to render panels dynamically from the active `LayoutConfig`:

1. Replace the hardcoded two-column grid with a CSS Grid driven by `LayoutConfig.columns` and `LayoutConfig.rows`.
2. Each `LayoutPanel` is rendered as a grid item at its configured position/span.
3. A component registry maps `panel.component` string to the actual Svelte component (using `{#if}` chains or a `<svelte:component>` approach).
4. The visualization panel, frequency display, band selector, mode selector, PTT, S-meter, audio controls, DSP panel, LUFS meter, preset selector, and extended CAT controls are all renderable panels.
5. Panels that are not in the current layout are simply not rendered.
6. The layout adapts to screen size -- on narrow screens, collapse to a single column.

**Done when**: The default "Voice Operating" layout renders identically to the current hardcoded layout. Switching to "Digital Modes" or "SWL" produces a different arrangement. `npm run build` passes.

---

### Task 34: Virtual device passthrough documentation

**Files**: `docs/virtual-passthrough.md` (new), `server/scripts/` (new directory, optional helper scripts)

Document how to use desktop applications with Riglet's remote radios:

1. **Virtual serial port** section:
   - Explain that rigctld's TCP port is directly usable by apps like WSJT-X (Hamlib NET rigctl).
   - Document `socat` command to create a local virtual serial port mapped to rigctld TCP.
   - Example for WSJT-X configuration.
   - Example for fldigi configuration.

2. **Virtual audio device** section:
   - PipeWire: document how to create a virtual sink/source pair and bridge it to Riglet's audio WebSocket.
   - JACK: similar documentation for JACK-based setups.
   - Reference a helper script concept (note: actual bridge daemon is future work).

3. **Network considerations**: note that the operator's LAN should have low latency for best experience.

**Done when**: Documentation is clear, includes copy-paste-ready commands, and covers the major use cases.

---

### Task 35: Extended CAT frontend controls (VFO, SWR, CTCSS)

**Files**: `ui/src/lib/components/VfoSelector.svelte` (new), `ui/src/lib/components/SwrMeter.svelte` (new), `ui/src/lib/components/CtcssSelector.svelte` (new)

Create UI components for the extended CAT features:

1. `VfoSelector.svelte`: Toggle between VFO A and VFO B. Shows active VFO. Sends `vfo` message via control WebSocket.
2. `SwrMeter.svelte`: Displays SWR reading as a bar meter (1.0 to 3.0+ range). Color coded: green (<1.5), yellow (1.5-2.5), red (>2.5). Only visible during TX (SWR is meaningless during RX).
3. `CtcssSelector.svelte`: Dropdown of standard CTCSS tones (67.0 Hz through 254.1 Hz, plus "Off"). Sends `ctcss` message via control WebSocket. Shows current tone setting.
4. All components: keyboard accessible, ARIA labeled, theme-aware.
5. Integrate as available layout panels.

**Done when**: VFO switching works. SWR meter shows during TX. CTCSS can be set and cleared. `npm run build` passes.

---

### Task 36: ModeSelector curated mode support

**Files**: `ui/src/lib/components/ModeSelector.svelte`, `ui/src/lib/api.ts`

Update ModeSelector to show only supported modes:

1. On mount, call `GET /api/radio/{radioId}/modes` (from task 6) to get the curated mode list.
2. Render only the modes returned by the API.
3. If the API call fails, fall back to the current generic mode list.
4. Cache the mode list per radio (it does not change at runtime).
5. Keyboard navigable.

**Done when**: ModeSelector shows only modes relevant to the connected radio model. `npm run build` passes.

---

### Task 37: Backend tests -- band plan, presets, config schema

**Files**: `server/tests/test_bandplan.py` (new), `server/tests/test_presets.py` (new), `server/tests/test_config_v2.py` (new)

Write pytest tests for new backend features:

1. `test_bandplan.py`:
   - `test_us_band_plan_has_expected_bands`: verify US plan includes 160m through 70cm.
   - `test_eu_band_plan_differs_from_us`: at least one band edge differs.
   - `test_unknown_region_raises`: `get_bands("xx")` raises ValueError.
   - `test_band_def_fields`: each BandDef has name, lower_mhz < upper_mhz, default_mode.

2. `test_presets.py`:
   - `test_create_preset`: POST creates and persists.
   - `test_update_preset`: PUT modifies existing.
   - `test_delete_preset`: DELETE removes.
   - `test_import_export_roundtrip`: import then export returns same data.
   - `test_preset_invalid_band_rejected`: preset with nonexistent band returns 409.

3. `test_config_v2.py`:
   - `test_region_field_default`: default config has region "us".
   - `test_invalid_region_rejected`: unknown region fails validation.
   - `test_radio_type_simulated`: config with type "simulated" passes validation without audio fields.
   - `test_radio_bands_validated`: bands not in region plan fail validation.
   - `test_presets_in_config`: presets round-trip through save/load.

**Done when**: All tests pass with `uv run pytest`. No test uses network or hardware.

---

### Task 38: Backend tests -- extended CAT, simulation type

**Files**: `server/tests/test_extended_cat.py` (new), `server/tests/test_simulation.py` (new)

Write pytest tests for extended CAT and simulation behavior:

1. `test_extended_cat.py`:
   - `test_get_vfo_simulation`: simulated radio returns "VFOA".
   - `test_set_vfo_simulation`: set_vfo stores new value.
   - `test_get_swr_simulation`: returns 1.0.
   - `test_get_ctcss_simulation`: returns 0.0.
   - `test_set_ctcss_simulation`: stores tone value.

2. `test_simulation.py`:
   - `test_simulated_radio_starts_online`: type "simulated" radio has online=True after startup.
   - `test_real_radio_unreachable_stays_offline`: type "real" radio with no rigctld has online=False, simulation=False.
   - `test_simulated_radio_returns_mock_data`: poll_once returns data without rigctld.
   - `test_real_radio_offline_no_mock_data`: poll_once raises or returns empty when offline (not mocked).

**Done when**: All tests pass with `uv run pytest`. Tests properly isolate without requiring rigctld.

---

### Task 39: Frontend build verification

**Agent**: @tester

Run `npm run build` from `ui/` and verify:
1. Build completes with zero errors.
2. No TypeScript type errors.
3. All new modules are included in the build output.
4. The `build/` directory contains the expected static files.

**Done when**: `npm run build` exits 0. Output directory contains index.html and JS bundles.

---

### Task 40: Full lint + type check pass

**Agent**: @tester

Run all quality checks and fix any issues:

1. `cd /Users/wells/Projects/riglet/server && uv run ruff check .` -- zero warnings.
2. `cd /Users/wells/Projects/riglet/server && uv run mypy .` -- zero errors.
3. `cd /Users/wells/Projects/riglet/server && uv run pytest` -- all tests pass.
4. `cd /Users/wells/Projects/riglet/ui && npm run build` -- zero errors.

**Done when**: All four commands exit 0 with clean output.
