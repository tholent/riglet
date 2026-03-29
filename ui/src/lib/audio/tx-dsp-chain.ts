/**
 * TxDspChain — client-side audio DSP processing chain for the TX path.
 *
 * Full chain (Wave 2):
 *   input(highpass) -> lowpass -> bass -> mid -> treble -> compressor -> limiter -> gateAnalyser(tap) -> gateNode -> output
 *
 * All stages are bypassed by default (pass-through). Build with build() before use.
 *
 * Usage:
 *   const chain = new TxDspChain(audioCtx);
 *   await chain.build();
 *   micSource.connect(chain.input);
 *   chain.output.connect(workletNode);
 */

export type CompressorPreset = 'light' | 'medium' | 'heavy' | 'manual';
export type LimiterPreset = 'soft' | 'medium' | 'hard' | 'manual';

export interface CompressorPresetParams {
	threshold: number;
	ratio: number;
	attack: number;
	release: number;
}

export interface LimiterPresetParams {
	threshold: number;
	ratio: number;
	attack: number;
	release: number;
}

export const LIMITER_PRESETS: Record<Exclude<LimiterPreset, 'manual'>, LimiterPresetParams> = {
	soft:   { threshold: -6,  ratio: 4,  attack: 0.005, release: 0.1  },
	medium: { threshold: -3,  ratio: 10, attack: 0.002, release: 0.05 },
	hard:   { threshold: -1,  ratio: 20, attack: 0.001, release: 0.025 },
};

export const COMPRESSOR_PRESETS: Record<Exclude<CompressorPreset, 'manual'>, CompressorPresetParams> = {
	light:  { threshold: -20, ratio: 2,  attack: 0.003, release: 0.25 },
	medium: { threshold: -24, ratio: 4,  attack: 0.003, release: 0.25 },
	heavy:  { threshold: -30, ratio: 8,  attack: 0.001, release: 0.1  },
};

export class TxDspChain {
	private ctx: AudioContext;

	// Filter nodes
	private highpassNode: BiquadFilterNode | null = null;
	private lowpassNode: BiquadFilterNode | null = null;

	// 3-band EQ nodes (Task 12)
	private bassNode: BiquadFilterNode | null = null;
	private midNode: BiquadFilterNode | null = null;
	private trebleNode: BiquadFilterNode | null = null;

	// Vocal compressor (Task 13)
	private compressorNode: DynamicsCompressorNode | null = null;

	// Limiter (Task 14)
	private limiterNode: DynamicsCompressorNode | null = null;

	// Noise gate (Task 15)
	private gateAnalyser: AnalyserNode | null = null;
	private gateNode: GainNode | null = null;
	private _gateInterval: ReturnType<typeof setInterval> | null = null;
	private _gateHoldTimer: ReturnType<typeof setTimeout> | null = null;
	private _gateOpen = true;

	// Enabled state
	private _highpassEnabled = false;
	private _lowpassEnabled = false;
	private _eqEnabled = false;
	private _compressorEnabled = false;
	private _compressorPreset: string = 'manual';
	private _limiterEnabled = false;
	private _limiterPreset: LimiterPreset = 'medium';
	private _gateEnabled = false;
	private _gateThreshold = -60;

	constructor(ctx: AudioContext) {
		this.ctx = ctx;
	}

	/** First node in the chain; connect your microphone source here. */
	get input(): AudioNode {
		return this.highpassNode!;
	}

	/** Last node in the chain; connect this to the PCM worklet or destination. */
	get output(): AudioNode {
		return this.gateNode!;
	}

	/**
	 * Allocate and wire all DSP nodes.
	 * Must be called once after construction, before connecting to the graph.
	 */
	async build(): Promise<void> {
		const ctx = this.ctx;

		// --- Highpass filter (bypassed: freq = 1 Hz) ---
		this.highpassNode = ctx.createBiquadFilter();
		this.highpassNode.type = 'highpass';
		this.highpassNode.frequency.value = 1;

		// --- Lowpass filter (bypassed: freq = Nyquist) ---
		this.lowpassNode = ctx.createBiquadFilter();
		this.lowpassNode.type = 'lowpass';
		this.lowpassNode.frequency.value = ctx.sampleRate / 2;

		// --- 3-band EQ (Task 12): all gains 0 = transparent ---
		this.bassNode = ctx.createBiquadFilter();
		this.bassNode.type = 'lowshelf';
		this.bassNode.frequency.value = 200;
		this.bassNode.gain.value = 0;

		this.midNode = ctx.createBiquadFilter();
		this.midNode.type = 'peaking';
		this.midNode.frequency.value = 1000;
		this.midNode.Q.value = 1.0;
		this.midNode.gain.value = 0;

		this.trebleNode = ctx.createBiquadFilter();
		this.trebleNode.type = 'highshelf';
		this.trebleNode.frequency.value = 3000;
		this.trebleNode.gain.value = 0;

		// --- Vocal compressor (Task 13): bypassed by default (ratio=1, threshold=0) ---
		this.compressorNode = ctx.createDynamicsCompressor();
		this.compressorNode.ratio.value = 1;
		this.compressorNode.threshold.value = 0;
		this.compressorNode.attack.value = 0.003;
		this.compressorNode.release.value = 0.25;
		this.compressorNode.knee.value = 6;

		// --- Limiter (Task 14): bypassed by default (ratio=1, threshold=0) ---
		this.limiterNode = ctx.createDynamicsCompressor();
		this.limiterNode.threshold.value = 0;
		this.limiterNode.ratio.value = 1;
		this.limiterNode.knee.value = 0;
		this.limiterNode.attack.value = 0.001;
		this.limiterNode.release.value = 0.01;

		// --- Noise gate analyser tap (Task 15) ---
		this.gateAnalyser = ctx.createAnalyser();
		this.gateAnalyser.fftSize = 256;

		// --- Noise gate gain (Task 15): open by default ---
		this.gateNode = ctx.createGain();
		this.gateNode.gain.value = 1;

		// Wire full chain:
		// highpass -> lowpass -> bass -> mid -> treble -> compressor -> limiter -> gateAnalyser -> gateNode
		this.highpassNode.connect(this.lowpassNode);
		this.lowpassNode.connect(this.bassNode);
		this.bassNode.connect(this.midNode);
		this.midNode.connect(this.trebleNode);
		this.trebleNode.connect(this.compressorNode);
		this.compressorNode.connect(this.limiterNode);
		this.limiterNode.connect(this.gateAnalyser);
		this.gateAnalyser.connect(this.gateNode);
	}

	/** Disconnect and release all nodes. */
	destroy(): void {
		if (this._gateInterval !== null) {
			clearInterval(this._gateInterval);
			this._gateInterval = null;
		}
		if (this._gateHoldTimer !== null) {
			clearTimeout(this._gateHoldTimer);
			this._gateHoldTimer = null;
		}
		this.highpassNode?.disconnect();
		this.lowpassNode?.disconnect();
		this.bassNode?.disconnect();
		this.midNode?.disconnect();
		this.trebleNode?.disconnect();
		this.compressorNode?.disconnect();
		this.limiterNode?.disconnect();
		this.gateAnalyser?.disconnect();
		this.gateNode?.disconnect();
		this.highpassNode = null;
		this.lowpassNode = null;
		this.bassNode = null;
		this.midNode = null;
		this.trebleNode = null;
		this.compressorNode = null;
		this.limiterNode = null;
		this.gateAnalyser = null;
		this.gateNode = null;
	}

	// ------------------------------------------------------------------
	// Highpass control
	// ------------------------------------------------------------------

	/** Set highpass cutoff frequency in Hz. */
	setHighpass(freqHz: number): void {
		if (!this.highpassNode) return;
		this.highpassNode.frequency.value = freqHz;
	}

	/** Enable or disable the highpass filter. Bypass sets freq to 1 Hz. */
	enableHighpass(enabled: boolean): void {
		if (!this.highpassNode) return;
		this._highpassEnabled = enabled;
		if (!enabled) {
			this.highpassNode.frequency.value = 1;
		}
	}

	isHighpassEnabled(): boolean {
		return this._highpassEnabled;
	}

	// ------------------------------------------------------------------
	// Lowpass control
	// ------------------------------------------------------------------

	/** Set lowpass cutoff frequency in Hz. */
	setLowpass(freqHz: number): void {
		if (!this.lowpassNode) return;
		this.lowpassNode.frequency.value = freqHz;
	}

	/** Enable or disable the lowpass filter. Bypass sets freq to Nyquist. */
	enableLowpass(enabled: boolean): void {
		if (!this.lowpassNode) return;
		this._lowpassEnabled = enabled;
		if (!enabled) {
			this.lowpassNode.frequency.value = this.ctx.sampleRate / 2;
		}
	}

	isLowpassEnabled(): boolean {
		return this._lowpassEnabled;
	}

	// ------------------------------------------------------------------
	// 3-band EQ control (Task 12)
	// ------------------------------------------------------------------

	/** Set bass shelf gain in dB. Clamped to -20..+20. */
	setBass(gainDb: number): void {
		if (!this.bassNode) return;
		this.bassNode.gain.value = Math.max(-20, Math.min(20, gainDb));
	}

	/** Set mid peaking gain in dB. Clamped to -20..+20. */
	setMid(gainDb: number): void {
		if (!this.midNode) return;
		this.midNode.gain.value = Math.max(-20, Math.min(20, gainDb));
	}

	/** Set treble shelf gain in dB. Clamped to -20..+20. */
	setTreble(gainDb: number): void {
		if (!this.trebleNode) return;
		this.trebleNode.gain.value = Math.max(-20, Math.min(20, gainDb));
	}

	/** Enable or disable the 3-band EQ. When disabled, all gains are zeroed. */
	enableEq(enabled: boolean): void {
		this._eqEnabled = enabled;
		if (!enabled) {
			if (this.bassNode) this.bassNode.gain.value = 0;
			if (this.midNode) this.midNode.gain.value = 0;
			if (this.trebleNode) this.trebleNode.gain.value = 0;
		}
	}

	isEqEnabled(): boolean {
		return this._eqEnabled;
	}

	// ------------------------------------------------------------------
	// Vocal compressor control (Task 13)
	// ------------------------------------------------------------------

	/** Apply a named compressor preset. */
	setCompressorPreset(preset: CompressorPreset): void {
		this._compressorPreset = preset;
		if (preset !== 'manual') {
			const p = COMPRESSOR_PRESETS[preset];
			this._applyCompressorParams(p.threshold, p.ratio, p.attack, p.release);
		}
	}

	/** Set compressor parameters manually (sets preset to 'manual'). */
	setCompressor(threshold: number, ratio: number, attack: number, release: number): void {
		this._compressorPreset = 'manual';
		this._applyCompressorParams(threshold, ratio, attack, release);
	}

	private _applyCompressorParams(
		threshold: number,
		ratio: number,
		attack: number,
		release: number,
	): void {
		if (!this.compressorNode) return;
		this.compressorNode.threshold.value = threshold;
		this.compressorNode.ratio.value = ratio;
		this.compressorNode.attack.value = attack;
		this.compressorNode.release.value = release;
	}

	/** Enable or disable the compressor. Bypass: ratio=1, threshold=0. */
	enableCompressor(enabled: boolean): void {
		if (!this.compressorNode) return;
		this._compressorEnabled = enabled;
		if (!enabled) {
			this.compressorNode.ratio.value = 1;
			this.compressorNode.threshold.value = 0;
		}
	}

	isCompressorEnabled(): boolean {
		return this._compressorEnabled;
	}

	getCompressorPreset(): string {
		return this._compressorPreset;
	}

	// ------------------------------------------------------------------
	// Limiter control (Task 14)
	// ------------------------------------------------------------------

	/** Apply a named limiter preset. */
	setLimiterPreset(preset: Exclude<LimiterPreset, 'manual'>): void {
		if (!this.limiterNode) return;
		this._limiterPreset = preset;
		const p = LIMITER_PRESETS[preset];
		this.limiterNode.threshold.value = p.threshold;
		this.limiterNode.ratio.value = p.ratio;
		this.limiterNode.attack.value = p.attack;
		this.limiterNode.release.value = p.release;
	}

	/** Set all limiter parameters manually. */
	setLimiter(thresholdDb: number, ratio: number, attackS: number, releaseS: number): void {
		if (!this.limiterNode) return;
		this._limiterPreset = 'manual';
		this.limiterNode.threshold.value = Math.max(-20, Math.min(0, thresholdDb));
		this.limiterNode.ratio.value = Math.max(1, Math.min(20, ratio));
		this.limiterNode.attack.value = Math.max(0.001, Math.min(0.1, attackS));
		this.limiterNode.release.value = Math.max(0.01, Math.min(1, releaseS));
	}

	/** Enable or disable the limiter. When enabling, applies the current preset. */
	enableLimiter(enabled: boolean): void {
		if (!this.limiterNode) return;
		this._limiterEnabled = enabled;
		if (enabled) {
			if (this._limiterPreset !== 'manual') {
				this.setLimiterPreset(this._limiterPreset);
			}
		} else {
			this.limiterNode.threshold.value = 0;
			this.limiterNode.ratio.value = 1;
		}
	}

	isLimiterEnabled(): boolean {
		return this._limiterEnabled;
	}

	// ------------------------------------------------------------------
	// Noise gate control (Task 15)
	// ------------------------------------------------------------------

	/** Set gate threshold in dBFS. Clamped to -100..0. */
	setGateThreshold(thresholdDb: number): void {
		this._gateThreshold = Math.max(-100, Math.min(0, thresholdDb));
	}

	/** Enable or disable the noise gate. When disabled, gate gain is always 1. */
	enableGate(enabled: boolean): void {
		this._gateEnabled = enabled;
		if (enabled) {
			this._startGatePolling();
		} else {
			this._stopGatePolling();
			// Ensure gate is open when disabled
			if (this.gateNode) this.gateNode.gain.value = 1;
			this._gateOpen = true;
		}
	}

	isGateEnabled(): boolean {
		return this._gateEnabled;
	}

	private _startGatePolling(): void {
		if (this._gateInterval !== null) return;
		this._gateInterval = setInterval(() => {
			this._tickGate();
		}, 50);
	}

	private _stopGatePolling(): void {
		if (this._gateInterval !== null) {
			clearInterval(this._gateInterval);
			this._gateInterval = null;
		}
		if (this._gateHoldTimer !== null) {
			clearTimeout(this._gateHoldTimer);
			this._gateHoldTimer = null;
		}
	}

	private _tickGate(): void {
		if (!this.gateAnalyser || !this.gateNode) return;

		const buf = new Float32Array(this.gateAnalyser.fftSize);
		this.gateAnalyser.getFloatTimeDomainData(buf);

		// Compute RMS
		let sumSq = 0;
		for (let i = 0; i < buf.length; i++) {
			sumSq += buf[i] * buf[i];
		}
		const rms = Math.sqrt(sumSq / buf.length);

		// Convert to dBFS (guard against log(0))
		const dbfs = rms > 0 ? 20 * Math.log10(rms) : -Infinity;

		if (dbfs >= this._gateThreshold) {
			// Signal above threshold — open gate, cancel any pending close
			if (this._gateHoldTimer !== null) {
				clearTimeout(this._gateHoldTimer);
				this._gateHoldTimer = null;
			}
			if (!this._gateOpen) {
				this._gateOpen = true;
				this.gateNode.gain.value = 1;
			}
		} else {
			// Signal below threshold — start 100ms hold timer before closing
			if (this._gateOpen && this._gateHoldTimer === null) {
				this._gateHoldTimer = setTimeout(() => {
					this._gateHoldTimer = null;
					this._gateOpen = false;
					if (this.gateNode) this.gateNode.gain.value = 0;
				}, 100);
			}
		}
	}
}
