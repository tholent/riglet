# Riglet -- Implementation Plan

---

## Feature: v0.3.0 -- Per-Radio DSP Chains

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
| 18 | RxDspPopover component                                           | P1       | @developer | [ ]    | 17         | Per-filter config panel with on/off toggle      |
| 19 | TxDspPanel component                                             | P1       | @developer | [x]    | 16         | Co-located with PTT, button to open menu        |
| 20 | TxDspMenu component                                              | P1       | @developer | [ ]    | 19         | Compressor presets, manual sliders, EQ, gate    |
| 21 | Integrate RxDspPillRow into main page layout                     | P0       | @developer | [ ]    | 17, 18     | `routes/+page.svelte`                           |
| 22 | Integrate TxDspPanel into PTT area                               | P0       | @developer | [ ]    | 19, 20     | `routes/+page.svelte`                           |
| 23 | Load DSP config from backend on radio connect                    | P0       | @developer | [ ]    | 02, 10, 16 | Fetch GET on WS open, apply to chains           |
| 24 | Debounced save DSP config to backend on parameter change         | P0       | @developer | [ ]    | 02, 23     | 500ms debounce, PATCH on change                 |
| 25 | Backend: unit tests for RxDspConfig and TxDspConfig validation   | P0       | @developer | [x]    | 01         | `tests/test_dsp_config.py`                      |
| 26 | Backend: integration tests for DSP config GET/PATCH              | P0       | @developer | [x]    | 02         | `tests/test_dsp_api.py`                         |
| 27 | Frontend: unit tests for RxDspChain node wiring                  | P0       | @developer | [x]    | 10         | Vitest, mock AudioContext                       |
| 28 | Frontend: unit tests for TxDspChain node wiring                  | P0       | @developer | [ ]    | 16         | Vitest, mock AudioContext                       |

---

### Parallelization Strategy

**Wave 1** (no dependencies, all independent):
- Task 01: Backend config schema
- Tasks 03-09: All individual RxDspChain filter nodes (can be developed independently as each is a self-contained node)
- Task 11: TxDspChain base class with highpass + lowpass

**Wave 2** (depends on Wave 1 outputs):
- Task 02: DSP config API (depends on 01)
- Task 10: Wire RxDspChain into AudioManager (depends on 03-09)
- Tasks 12-15: TxDspChain additional stages (depend on 11)
- Task 25: Backend schema tests (depends on 01)

**Wave 3** (depends on Wave 2):
- Task 16: Wire TxDspChain into AudioManager (depends on 11-15)
- Task 17: RxDspPillRow component (depends on 10)
- Task 19: TxDspPanel component (depends on 16)
- Task 26: Backend API integration tests (depends on 02)
- Task 27: RxDspChain unit tests (depends on 10)

**Wave 4** (depends on Wave 3):
- Task 18: RxDspPopover component (depends on 17)
- Task 20: TxDspMenu component (depends on 19)
- Task 28: TxDspChain unit tests (depends on 16)

**Wave 5** (integration, depends on Wave 4):
- Task 21: Integrate RxDspPillRow into main page (depends on 17, 18)
- Task 22: Integrate TxDspPanel into PTT area (depends on 19, 20)
- Task 23: Load DSP config from backend on connect (depends on 02, 10, 16)

**Wave 6** (final, depends on Wave 5):
- Task 24: Debounced save DSP config on change (depends on 02, 23)

---

### Task Descriptions

#### Task 01: Config schema -- add RxDspConfig and TxDspConfig Pydantic models

**File:** `server/config.py`

Add two new Pydantic v2 `BaseModel` subclasses and nest them as optional fields on `RadioConfig`.

**RxDspConfig fields:**
- `highpass_enabled: bool = False`
- `highpass_freq: int = 100` (range 50-500 Hz, field_validator)
- `lowpass_enabled: bool = False`
- `lowpass_freq: int = 3000` (range 1500-5000 Hz, field_validator)
- `peak_enabled: bool = False`
- `peak_freq: int = 1000` (range 200-4000 Hz)
- `peak_gain: float = 0.0` (range -20.0 to +20.0 dB)
- `peak_q: float = 1.0` (range 0.1-30.0)
- `noise_blanker_enabled: bool = False`
- `noise_blanker_freq: int = 50` (literal 50 or 60)
- `notch_enabled: bool = False`
- `notch_mode: Literal["manual", "auto"] = "manual"`
- `notch_freq: int = 1000` (range 100-5000 Hz)
- `notch_q: float = 10.0` (range 1.0-50.0)
- `bandpass_enabled: bool = False`
- `bandpass_preset: Literal["voice", "cw", "manual"] = "voice"`
- `bandpass_center: int = 1500` (Hz)
- `bandpass_width: int = 2400` (Hz)
- `nr_enabled: bool = False`
- `nr_amount: float = 0.5` (range 0.0-1.0)

**TxDspConfig fields:**
- `highpass_enabled: bool = False`
- `highpass_freq: int = 100` (range 50-500 Hz)
- `lowpass_enabled: bool = False`
- `lowpass_freq: int = 3000` (range 1500-5000 Hz)
- `eq_enabled: bool = False`
- `eq_bass_gain: float = 0.0` (dB, -20 to +20)
- `eq_mid_gain: float = 0.0` (dB, -20 to +20)
- `eq_treble_gain: float = 0.0` (dB, -20 to +20)
- `compressor_enabled: bool = False`
- `compressor_preset: Literal["off", "light", "medium", "heavy", "manual"] = "off"`
- `compressor_threshold: float = -24.0` (dBFS)
- `compressor_ratio: float = 4.0`
- `compressor_attack: float = 0.003` (seconds)
- `compressor_release: float = 0.25` (seconds)
- `limiter_enabled: bool = False`
- `limiter_threshold: float = -3.0` (dBFS)
- `gate_enabled: bool = False`
- `gate_threshold: float = -60.0` (dBFS, range -100 to 0)

**Nest on RadioConfig:**
```python
rx_dsp: RxDspConfig = RxDspConfig()
tx_dsp: TxDspConfig = TxDspConfig()
```

Both default to all-disabled so existing configs are backward-compatible.

**Acceptance criteria:**
- `load_config` / `save_config` round-trip with DSP fields present and absent
- Validators reject out-of-range values with clear error messages
- Existing `RadioConfig` tests still pass

---

#### Task 02: DSP config API -- GET/PATCH per-radio DSP settings endpoint

**File:** `server/routers/dsp.py` (new file)

Create a new APIRouter mounted in `main.py` at the `/api` prefix.

**Endpoints:**

`GET /api/radios/{radio_id}/dsp`
- Returns `{"rx": <RxDspConfig dict>, "tx": <TxDspConfig dict>}`
- Uses `get_radio` dependency (404 if radio not found)
- Reads from the live config (`manager.config.radios[radio_id]`)

`PATCH /api/radios/{radio_id}/dsp`
- Request body: `{"rx": {<partial RxDspConfig fields>}, "tx": {<partial TxDspConfig fields>}}`
- Both `rx` and `tx` keys are optional; missing keys mean "no change"
- Merges partial updates onto existing config using `model_copy(update=...)`
- Validates merged result (Pydantic validators run on copy)
- Persists to disk via `save_config`
- Returns the updated full DSP config (same shape as GET)
- 409 on validation errors (RFC 7807 format, consistent with existing pattern)

**Wire into main.py:**
- Import `dsp_router` from `routers.dsp`
- `app.include_router(dsp_router, prefix="/api")`

**Acceptance criteria:**
- GET returns defaults for a radio with no DSP config
- PATCH with partial RX updates does not reset TX config
- PATCH with invalid values returns 409 with problem details
- Config file on disk reflects changes after PATCH

---

#### Task 03: RxDspChain -- highpass filter node (100-300 Hz)

**File:** `ui/src/lib/audio/rx-dsp-chain.ts` (new file)

Create a new `RxDspChain` class that will replace the existing `DspChain`. This task creates the class skeleton and the first filter node.

**Class structure:**
```typescript
export class RxDspChain {
    private ctx: AudioContext;
    // Node declarations
    private highpassNode: BiquadFilterNode | null = null;
    // ... (other nodes added in tasks 04-09)

    get input(): AudioNode { ... }  // first node in chain
    get output(): AudioNode { ... } // last node in chain

    async build(): Promise<void> { ... }
    destroy(): void { ... }
}
```

**Highpass node:**
- `BiquadFilterNode` with `type = 'highpass'`
- Default frequency: 100 Hz
- Bypassed by default: frequency set to 1 Hz (below audible range)
- `setHighpass(freqHz: number)`: set cutoff frequency (clamped 50-500)
- `enableHighpass(enabled: boolean)`: toggle; when disabled, freq = 1 Hz
- `isHighpassEnabled(): boolean`

**Acceptance criteria:**
- Class instantiates with an AudioContext
- `build()` creates the highpass BiquadFilterNode
- Enable/disable toggles the effective cutoff

---

#### Task 04: RxDspChain -- lowpass filter node (2.5-3.5 kHz)

**File:** `ui/src/lib/audio/rx-dsp-chain.ts`

Add lowpass filter node to `RxDspChain`.

**Lowpass node:**
- `BiquadFilterNode` with `type = 'lowpass'`
- Default frequency: 3000 Hz
- Bypassed by default: frequency set to `ctx.sampleRate / 2` (Nyquist)
- `setLowpass(freqHz: number)`: set cutoff (clamped 1500-5000)
- `enableLowpass(enabled: boolean)`: toggle; when disabled, freq = Nyquist
- `isLowpassEnabled(): boolean`

Wire into chain: highpass -> lowpass -> (rest of chain)

---

#### Task 05: RxDspChain -- peak filter node

**File:** `ui/src/lib/audio/rx-dsp-chain.ts`

Add peak (parametric EQ) filter node to `RxDspChain`.

**Peak node:**
- `BiquadFilterNode` with `type = 'peaking'`
- Default: freq 1000 Hz, gain 0 dB, Q 1.0
- Bypassed by default: gain = 0 dB (transparent)
- `setPeak(freqHz: number, gainDb: number, q: number)`: set all params
- `enablePeak(enabled: boolean)`: toggle; when disabled, gain = 0
- `isPeakEnabled(): boolean`

Wire into chain: highpass -> lowpass -> peak -> (rest)

---

#### Task 06: RxDspChain -- noise blanker node (biquad notch at 50/60 Hz)

**File:** `ui/src/lib/audio/rx-dsp-chain.ts`

Add a power-line noise blanker to `RxDspChain`.

**Noise blanker node:**
- `BiquadFilterNode` with `type = 'notch'`
- Default frequency: 50 Hz, Q = 30 (narrow notch)
- Bypassed by default: Q = 0.01 (effectively transparent)
- `setNoiseBlankerFreq(freq: 50 | 60)`: switch between 50 Hz and 60 Hz mains hum
- `enableNoiseBlanker(enabled: boolean)`: toggle; when disabled, Q = 0.01
- `isNoiseBlankerEnabled(): boolean`

Wire into chain: highpass -> lowpass -> peak -> noiseBlanker -> (rest)

---

#### Task 07: RxDspChain -- notch filter node (auto/manual)

**File:** `ui/src/lib/audio/rx-dsp-chain.ts`

Add a notch filter with manual and auto modes to `RxDspChain`.

**Notch node:**
- `BiquadFilterNode` with `type = 'notch'`
- Manual mode: operator sets center frequency and Q
- Auto mode: placeholder for future tone detection (for now, defaults to 1000 Hz; auto-detect logic is out of scope for this task -- set a TODO comment)
- Default: freq 1000 Hz, Q = 10
- Bypassed by default: Q = 0.01
- `setNotch(centerHz: number, q: number)`: manual params
- `setNotchMode(mode: 'manual' | 'auto')`: store mode flag
- `enableNotch(enabled: boolean)`: toggle; when disabled, Q = 0.01
- `isNotchEnabled(): boolean`
- `getNotchMode(): 'manual' | 'auto'`

Wire into chain: highpass -> lowpass -> peak -> noiseBlanker -> notch -> (rest)

---

#### Task 08: RxDspChain -- bandpass filter (presets + manual range)

**File:** `ui/src/lib/audio/rx-dsp-chain.ts`

Add a bandpass filter with presets to `RxDspChain`.

**Bandpass node:**
- `BiquadFilterNode` with `type = 'bandpass'`
- Presets:
  - `"voice"`: center 1500 Hz, width 2400 Hz (Q = 1500/2400 = 0.625)
  - `"cw"`: center 700 Hz, width 500 Hz (Q = 1.4)
  - `"manual"`: operator-specified center and width
- Default: voice preset
- Bypassed by default: Q = 0.01 (wide open)
- `setBandpassPreset(preset: 'voice' | 'cw' | 'manual')`: apply preset center/width
- `setBandpass(centerHz: number, widthHz: number)`: manual params (also sets preset to 'manual')
- `enableBandpass(enabled: boolean)`: toggle; when disabled, Q = 0.01
- `isBandpassEnabled(): boolean`
- `getBandpassPreset(): string`

Wire into chain: highpass -> lowpass -> peak -> noiseBlanker -> notch -> bandpass -> (rest)

---

#### Task 09: RxDspChain -- DSP noise reduction AudioWorklet

**File:** `ui/src/lib/audio/rx-dsp-chain.ts` (node integration) and `ui/static/nr-worklet.js` (already exists, verify compatibility)

Add NR AudioWorklet node to `RxDspChain`.

**NR node:**
- Reuse existing `nr-worklet.js` processor (spectral subtraction)
- Load via `ctx.audioWorklet.addModule('/nr-worklet.js')` (best-effort, graceful fallback if unavailable)
- `setNrAmount(amount: number)`: 0.0-1.0 via AudioParam `'amount'`
- `enableNr(enabled: boolean)`: via AudioParam `'enabled'` (0/1)
- `isNrEnabled(): boolean`
- `isNrAvailable(): boolean`
- If worklet fails to load, skip NR node in chain wiring (connect previous node directly to next)

Wire into chain: highpass -> lowpass -> peak -> noiseBlanker -> notch -> bandpass -> NR -> output

**Final full chain order:**
`input(highpass) -> lowpass -> peak -> noiseBlanker -> notch -> bandpass -> NR -> output`

---

#### Task 10: Wire RxDspChain into AudioManager RX playback path

**Files:**
- `ui/src/lib/audio/audio-manager.ts`
- `ui/src/lib/audio/rx-dsp-chain.ts`

Replace the existing `DspChain` import and usage with `RxDspChain`.

**Changes to AudioManager:**
- Replace `import { DspChain }` with `import { RxDspChain }`
- Replace `private dspChain: DspChain | null` with `private rxDspChain: RxDspChain | null`
- In `init()`: instantiate `RxDspChain`, call `await rxDspChain.build()`, wire:
  `workletNode -> rxDspChain.input` and `rxDspChain.output -> squelchNode -> gainNode -> destination`
- Expose `getRxDspChain(): RxDspChain | null` getter for UI components to call
- In `destroy()`: call `rxDspChain.destroy()`
- Remove old `DspChain` references

**Backward compatibility:**
- The existing `DspPanel.svelte` component imports `DspChain` type. Update its import to `RxDspChain` and adjust property access to match new API.
- Ensure all existing DSP panel functionality (bandpass, notch, NR, compressor, EQ) still works via the new chain

**Acceptance criteria:**
- Audio plays through the RX DSP chain
- All existing DSP controls still function
- No TypeScript errors from `npm run build`

---

#### Task 11: TxDspChain -- highpass + lowpass filter nodes

**File:** `ui/src/lib/audio/tx-dsp-chain.ts` (new file)

Create a new `TxDspChain` class for the TX audio path.

**Class structure:**
```typescript
export class TxDspChain {
    private ctx: AudioContext;
    private highpassNode: BiquadFilterNode | null = null;
    private lowpassNode: BiquadFilterNode | null = null;
    // ... (other nodes in tasks 12-15)

    get input(): AudioNode { ... }
    get output(): AudioNode { ... }

    async build(): Promise<void> { ... }
    destroy(): void { ... }
}
```

**Highpass node:**
- `BiquadFilterNode`, `type = 'highpass'`, default 100 Hz
- Bypassed by default: freq = 1 Hz
- `setHighpass(freqHz: number)`, `enableHighpass(enabled: boolean)`, `isHighpassEnabled(): boolean`

**Lowpass node:**
- `BiquadFilterNode`, `type = 'lowpass'`, default 3000 Hz
- Bypassed by default: freq = Nyquist
- `setLowpass(freqHz: number)`, `enableLowpass(enabled: boolean)`, `isLowpassEnabled(): boolean`

Wire: highpass -> lowpass -> output

---

#### Task 12: TxDspChain -- 3-band EQ (3x BiquadFilterNode)

**File:** `ui/src/lib/audio/tx-dsp-chain.ts`

Add 3-band EQ to `TxDspChain`.

**Nodes:**
- `bassNode`: `BiquadFilterNode`, `type = 'lowshelf'`, freq 200 Hz, default gain 0 dB
- `midNode`: `BiquadFilterNode`, `type = 'peaking'`, freq 1000 Hz, Q 1.0, default gain 0 dB
- `trebleNode`: `BiquadFilterNode`, `type = 'highshelf'`, freq 3000 Hz, default gain 0 dB
- Bypassed by default: all gains = 0 dB
- `setBass(gainDb: number)`, `setMid(gainDb: number)`, `setTreble(gainDb: number)`: range -20 to +20
- `enableEq(enabled: boolean)`: toggle; when disabled, all gains = 0
- `isEqEnabled(): boolean`

Wire: highpass -> lowpass -> bass -> mid -> treble -> (rest)

---

#### Task 13: TxDspChain -- vocal compressor (DynamicsCompressorNode)

**File:** `ui/src/lib/audio/tx-dsp-chain.ts`

Add vocal compressor with presets to `TxDspChain`.

**Compressor node:**
- `DynamicsCompressorNode`
- Presets (define as a `Record<string, CompressorParams>` constant):
  - `"light"`: threshold -20, ratio 2, attack 0.003, release 0.25
  - `"medium"`: threshold -24, ratio 4, attack 0.003, release 0.25
  - `"heavy"`: threshold -30, ratio 8, attack 0.001, release 0.1
  - `"manual"`: use whatever the operator sets
- Bypassed by default: ratio = 1, threshold = 0
- `setCompressorPreset(preset: 'light' | 'medium' | 'heavy' | 'manual')`: apply preset values
- `setCompressor(threshold: number, ratio: number, attack: number, release: number)`: manual params (also sets preset to 'manual')
- `enableCompressor(enabled: boolean)`: toggle
- `isCompressorEnabled(): boolean`
- `getCompressorPreset(): string`

Wire: ... -> treble -> compressor -> (rest)

---

#### Task 14: TxDspChain -- limiter stage (DynamicsCompressorNode, high ratio)

**File:** `ui/src/lib/audio/tx-dsp-chain.ts`

Add a limiter as the last dynamics stage in `TxDspChain`.

**Limiter node:**
- `DynamicsCompressorNode` configured as a hard limiter
- Default: threshold -3 dBFS, ratio 20, knee 0, attack 0.001s, release 0.01s
- Bypassed by default: ratio = 1, threshold = 0
- `setLimiterThreshold(thresholdDb: number)`: range -20 to 0
- `enableLimiter(enabled: boolean)`: toggle
- `isLimiterEnabled(): boolean`

Wire: ... -> compressor -> limiter -> (rest)

---

#### Task 15: TxDspChain -- noise gate (threshold-based gate node)

**File:** `ui/src/lib/audio/tx-dsp-chain.ts`

Add a noise gate to `TxDspChain`.

**Gate implementation:**
- Use a `GainNode` (gateNode) whose gain is snapped to 0 or 1
- Use an `AnalyserNode` feeding a periodic check (via `requestAnimationFrame` or a `setInterval` at 50ms) that computes RMS of the input signal
- If RMS (in dBFS) is above `gateThreshold`, gain = 1 (open); otherwise gain = 0 (closed)
- Add a hold timer (default 100ms) to prevent chatter
- `setGateThreshold(thresholdDb: number)`: range -100 to 0
- `enableGate(enabled: boolean)`: toggle; when disabled, gain always = 1
- `isGateEnabled(): boolean`
- `destroy()` must clear the interval/RAF

**Final full TX chain order:**
`input(highpass) -> lowpass -> bass -> mid -> treble -> compressor -> limiter -> gateAnalyser + gateNode -> output`

The analyser taps the signal before the gate node for level measurement.

Wire: ... -> limiter -> analyser (tap) -> gateNode -> output

---

#### Task 16: Wire TxDspChain into AudioManager TX capture path

**File:** `ui/src/lib/audio/audio-manager.ts`

Insert `TxDspChain` into the TX audio path, between the microphone source and the PCM worklet node.

**Changes to AudioManager:**
- Add `import { TxDspChain }` from `./tx-dsp-chain.js`
- Add `private txDspChain: TxDspChain | null = null`
- In TX start path (where `micSource` is connected):
  - Instantiate `TxDspChain`, call `await txDspChain.build()`
  - Wire: `micSource -> txDspChain.input` and `txDspChain.output -> workletNode` (TX input)
  - Previously: `micSource -> workletNode` directly
- Expose `getTxDspChain(): TxDspChain | null` getter
- In TX stop / `destroy()`: call `txDspChain.destroy()`

**Acceptance criteria:**
- TX audio passes through the TX DSP chain
- When all TX DSP stages are disabled (default), audio is bit-identical to bypass
- No TypeScript errors from `npm run build`

---

#### Task 17: RxDspPillRow component

**File:** `ui/src/lib/components/RxDspPillRow.svelte` (new file)

A horizontal row of pill-shaped buttons, one per RX DSP stage, displayed below the frequency display.

**Props:**
- `rxDspChain: RxDspChain | null`

**Pills (one per filter):**
- Highpass, Lowpass, Peak, NB (noise blanker), Notch, Bandpass, NR
- Each pill shows the filter name (abbreviated)
- Active (enabled) pills use an accent color (e.g., `bg-sky-500 text-white`)
- Inactive pills use a muted style (e.g., `bg-gray-700 text-gray-400`)
- Click on a pill opens the `RxDspPopover` for that filter (Task 18)
- If `rxDspChain` is null, all pills are disabled/grayed

**Accessibility:**
- Each pill is a `<button>` with `aria-pressed` reflecting enabled state
- Keyboard navigable (tab order)

---

#### Task 18: RxDspPopover component

**File:** `ui/src/lib/components/RxDspPopover.svelte` (new file)

A popover/dropdown panel that appears when an RX DSP pill is clicked, showing controls for that specific filter.

**Props:**
- `rxDspChain: RxDspChain | null`
- `filter: 'highpass' | 'lowpass' | 'peak' | 'noiseBlanker' | 'notch' | 'bandpass' | 'nr'`
- `open: boolean` (bindable)
- `anchor: HTMLElement | null` (for positioning)

**Content per filter:**
- **Highpass**: on/off toggle, frequency slider (50-500 Hz)
- **Lowpass**: on/off toggle, frequency slider (1500-5000 Hz)
- **Peak**: on/off toggle, frequency slider, gain slider (-20 to +20 dB), Q slider (0.1-30)
- **Noise Blanker**: on/off toggle, 50/60 Hz radio buttons
- **Notch**: on/off toggle, mode selector (manual/auto), frequency slider, Q slider
- **Bandpass**: on/off toggle, preset pills (voice/CW/manual), center+width sliders (when manual)
- **NR**: on/off toggle, amount slider (0-100%)

**Behavior:**
- Changes apply immediately to `rxDspChain` (call the appropriate setter)
- Emit a `change` event with the current filter state (for persistence layer, Task 24)
- Close on click-outside or Escape key

**Accessibility:**
- Focus trap when open
- Escape closes
- Sliders use `<input type="range">` with `aria-label`

---

#### Task 19: TxDspPanel component

**File:** `ui/src/lib/components/TxDspPanel.svelte` (new file)

A button co-located with the PTT button area that opens the TX DSP menu.

**Props:**
- `txDspChain: TxDspChain | null`

**UI:**
- A single button labeled "TX DSP" or a gear icon
- Badge/indicator showing number of active TX DSP stages (e.g., "3" if 3 stages enabled)
- Click opens `TxDspMenu` (Task 20) as a slide-up panel or popover

**Accessibility:**
- `<button>` with `aria-expanded` and `aria-haspopup="dialog"`
- Keyboard accessible

---

#### Task 20: TxDspMenu component

**File:** `ui/src/lib/components/TxDspMenu.svelte` (new file)

A menu/panel for configuring all TX DSP stages.

**Props:**
- `txDspChain: TxDspChain | null`
- `open: boolean` (bindable)

**Sections (collapsible):**
1. **Filters**: highpass on/off + freq slider, lowpass on/off + freq slider
2. **EQ**: on/off toggle, bass/mid/treble gain sliders (-20 to +20 dB)
3. **Compressor**: on/off toggle, preset pills (light/medium/heavy/manual), when manual: threshold/ratio/attack/release sliders
4. **Limiter**: on/off toggle, threshold slider (-20 to 0 dB)
5. **Gate**: on/off toggle, threshold slider (-100 to 0 dB)

**Behavior:**
- Changes apply immediately to `txDspChain`
- Emit `change` event for persistence (Task 24)
- Close on click-outside or Escape

**Accessibility:**
- Focus trap, Escape closes
- Collapsible sections use `<details>/<summary>` or equivalent with `aria-expanded`

---

#### Task 21: Integrate RxDspPillRow into main page layout

**File:** `ui/src/routes/+page.svelte`

**Changes:**
- Import `RxDspPillRow` from `$lib/components/RxDspPillRow.svelte`
- Place `<RxDspPillRow rxDspChain={audioManager?.getRxDspChain()} />` below the `FrequencyDisplay` component, above the waterfall
- Pass the `RxDspChain` instance obtained from `AudioManager.getRxDspChain()`
- Wire `change` events from pill row to the persistence layer (Task 24)

**Acceptance criteria:**
- Pill row renders on the main page
- Clicking a pill opens its popover
- Toggling a filter audibly affects RX audio

---

#### Task 22: Integrate TxDspPanel into PTT area

**File:** `ui/src/routes/+page.svelte`

**Changes:**
- Import `TxDspPanel` from `$lib/components/TxDspPanel.svelte`
- Place `<TxDspPanel txDspChain={audioManager?.getTxDspChain()} />` adjacent to the `PttButton` component
- Wire `change` events to persistence layer (Task 24)

**Acceptance criteria:**
- TX DSP button renders next to PTT
- Opening the menu shows all TX DSP controls
- Toggling a TX DSP stage audibly affects transmitted audio

---

#### Task 23: Load DSP config from backend on radio connect

**Files:**
- `ui/src/lib/api.ts` -- add `getDspConfig(radioId: string)` and `patchDspConfig(radioId: string, patch: object)` functions
- `ui/src/routes/+page.svelte` or appropriate connection handler

**getDspConfig:**
- `GET /api/radios/{radioId}/dsp`
- Returns `{ rx: RxDspConfig, tx: TxDspConfig }`
- TypeScript interfaces matching backend schema

**patchDspConfig:**
- `PATCH /api/radios/{radioId}/dsp`
- Accepts partial `{ rx?: Partial<RxDspConfig>, tx?: Partial<TxDspConfig> }`
- Returns updated full config

**Load on connect:**
- After `AudioManager` is initialized and DSP chains are built, call `getDspConfig(radioId)`
- Apply returned RX config values to `RxDspChain` (call each setter: `enableHighpass`, `setHighpass`, etc.)
- Apply returned TX config values to `TxDspChain`
- If GET fails (e.g., network error), log warning and use defaults (all disabled)

**Acceptance criteria:**
- On page load with a configured radio, DSP settings are restored from backend
- If backend has no DSP config (defaults), all filters start disabled

---

#### Task 24: Debounced save DSP config to backend on parameter change

**Files:**
- `ui/src/routes/+page.svelte` or a new `ui/src/lib/dsp-persistence.ts` utility

**Implementation:**
- Create a `DspPersistence` class or utility:
  - Holds the current radio ID and a 500ms debounce timer
  - `saveRx(partialConfig: Partial<RxDspConfig>)`: debounced PATCH with `{ rx: partialConfig }`
  - `saveTx(partialConfig: Partial<TxDspConfig>)`: debounced PATCH with `{ tx: partialConfig }`
  - On debounce fire: calls `patchDspConfig(radioId, pendingPatch)` from `api.ts`
  - Merges multiple rapid changes into one PATCH (accumulate partial updates during debounce window)
- Wire `change` events from `RxDspPillRow`/`RxDspPopover` to `saveRx()`
- Wire `change` events from `TxDspPanel`/`TxDspMenu` to `saveTx()`
- On PATCH failure: log error, do not retry (settings are still applied locally, just not persisted)

**Acceptance criteria:**
- Changing a filter parameter triggers a PATCH after 500ms of inactivity
- Rapid successive changes are batched into a single PATCH
- Reloading the page restores the last-saved settings

---

#### Task 25: Backend unit tests for RxDspConfig and TxDspConfig schema validation

**File:** `server/tests/test_dsp_config.py` (new file)

**Test cases:**
- `test_rx_dsp_config_defaults`: `RxDspConfig()` produces all-disabled defaults
- `test_tx_dsp_config_defaults`: `TxDspConfig()` produces all-disabled defaults
- `test_rx_dsp_highpass_freq_range`: values below 50 and above 500 raise `ValidationError`
- `test_rx_dsp_lowpass_freq_range`: values below 1500 and above 5000 raise `ValidationError`
- `test_rx_dsp_noise_blanker_freq_values`: only 50 and 60 accepted
- `test_rx_dsp_notch_mode_literal`: only "manual" and "auto" accepted
- `test_rx_dsp_bandpass_preset_literal`: only "voice", "cw", "manual" accepted
- `test_rx_dsp_nr_amount_range`: values below 0.0 and above 1.0 raise `ValidationError`
- `test_tx_dsp_compressor_preset_literal`: only "off", "light", "medium", "heavy", "manual" accepted
- `test_tx_dsp_gate_threshold_range`: values below -100 and above 0 raise `ValidationError`
- `test_radio_config_with_dsp_roundtrip`: `RadioConfig` with nested DSP configs serializes and deserializes correctly
- `test_radio_config_without_dsp_backward_compat`: `RadioConfig` dict without `rx_dsp`/`tx_dsp` keys parses with defaults

**Acceptance criteria:**
- All tests pass with `uv run pytest tests/test_dsp_config.py`

---

#### Task 26: Backend integration tests for DSP config GET/PATCH

**File:** `server/tests/test_dsp_api.py` (new file)

Use `httpx.AsyncClient` with FastAPI `TestClient` pattern (or `pytest-asyncio` + `app` fixture).

**Test cases:**
- `test_get_dsp_config_defaults`: GET returns all-disabled defaults for a valid radio
- `test_get_dsp_config_404`: GET with nonexistent radio_id returns 404
- `test_patch_rx_dsp_partial`: PATCH `{"rx": {"highpass_enabled": true, "highpass_freq": 200}}` updates only those fields, TX unchanged
- `test_patch_tx_dsp_partial`: PATCH `{"tx": {"compressor_enabled": true, "compressor_preset": "medium"}}` updates only those fields, RX unchanged
- `test_patch_dsp_invalid_value_409`: PATCH with out-of-range value returns 409 with RFC 7807 body
- `test_patch_dsp_persists_to_disk`: After PATCH, reload config from disk and verify DSP values present
- `test_patch_dsp_empty_body_noop`: PATCH `{}` returns current config unchanged

**Acceptance criteria:**
- All tests pass with `uv run pytest tests/test_dsp_api.py`

---

#### Task 27: Frontend unit tests for RxDspChain node wiring and parameter application

**File:** `ui/src/lib/audio/rx-dsp-chain.test.ts` (new file)

Use Vitest with a mock/stub `AudioContext` (e.g., `standardized-audio-context-mock` or manual mocks).

**Test cases:**
- `test_build_creates_all_nodes`: After `build()`, all node properties are non-null (except NR which may be null if worklet fails)
- `test_chain_order`: `input` is the highpass node, `output` is the last node (NR or bandpass if NR unavailable)
- `test_highpass_enable_disable`: enabling sets freq to configured value, disabling sets freq to 1 Hz
- `test_lowpass_enable_disable`: enabling sets freq to configured value, disabling sets freq to Nyquist
- `test_bandpass_presets`: setting "voice" preset applies center=1500/width=2400, "cw" applies center=700/width=500
- `test_notch_enable_disable`: enabling sets Q to configured value, disabling sets Q to 0.01
- `test_noise_blanker_freq_switch`: setting 60 Hz changes notch frequency to 60
- `test_nr_amount_clamped`: values outside 0-1 are clamped
- `test_destroy_disconnects_all`: after `destroy()`, all node refs are null

**Acceptance criteria:**
- All tests pass with `npm test` (Vitest)

---

#### Task 28: Frontend unit tests for TxDspChain node wiring and parameter application

**File:** `ui/src/lib/audio/tx-dsp-chain.test.ts` (new file)

Use Vitest with mock AudioContext.

**Test cases:**
- `test_build_creates_all_nodes`: After `build()`, all node properties are non-null
- `test_chain_order`: `input` is highpass, `output` is gateNode
- `test_highpass_enable_disable`: enabling/disabling toggles cutoff
- `test_lowpass_enable_disable`: enabling/disabling toggles cutoff
- `test_eq_enable_disable`: enabling preserves gain values, disabling zeros all gains
- `test_compressor_presets`: each preset applies correct threshold/ratio/attack/release values
- `test_compressor_manual_override`: setting manual params changes preset to "manual"
- `test_limiter_enable_disable`: enabling applies threshold, disabling sets ratio=1/threshold=0
- `test_gate_enable_disable`: enabling allows gate to close (gain=0), disabling forces gain=1
- `test_destroy_cleans_up`: after `destroy()`, all node refs are null and interval/RAF cleared

**Acceptance criteria:**
- All tests pass with `npm test` (Vitest)
