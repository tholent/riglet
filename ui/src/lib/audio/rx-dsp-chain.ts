/**
 * RxDspChain — client-side audio DSP processing chain for the RX path.
 *
 * Chain order:
 *   highpass -> lowpass -> peak -> noiseBlanker -> notch -> bandpass -> NR (if available)
 *
 * All stages are bypassed by default (pass-through). Build with build() before use.
 *
 * Usage:
 *   const chain = new RxDspChain(audioCtx);
 *   await chain.build();
 *   sourceNode.connect(chain.input);
 *   chain.output.connect(destinationNode);
 */

/** Bandpass preset definitions. */
const BANDPASS_PRESETS: Record<'voice' | 'cw', { centerHz: number; widthHz: number }> = {
	voice: { centerHz: 1500, widthHz: 2400 },
	cw: { centerHz: 700, widthHz: 500 },
};

export class RxDspChain {
	private ctx: AudioContext;

	// Filter nodes — all created in build()
	private highpassNode: BiquadFilterNode | null = null;
	private lowpassNode: BiquadFilterNode | null = null;
	private peakNode: BiquadFilterNode | null = null;
	private noiseBlankerNode: BiquadFilterNode | null = null;
	private notchNode: BiquadFilterNode | null = null;
	private bandpassNode: BiquadFilterNode | null = null;
	private nrNode: AudioWorkletNode | null = null;

	// Enabled state
	private _highpassEnabled = false;
	private _lowpassEnabled = false;
	private _peakEnabled = false;
	private _noiseBlankerEnabled = false;
	private _notchEnabled = false;
	private _notchMode: 'manual' | 'auto' = 'manual';
	private _bandpassEnabled = false;
	private _bandpassPreset: 'voice' | 'cw' | 'manual' = 'voice';
	private _nrEnabled = false;
	private _nrAvailable = false;

	constructor(ctx: AudioContext) {
		this.ctx = ctx;
	}

	/** First node in the chain; connect your source here. */
	get input(): AudioNode {
		return this.highpassNode!;
	}

	/**
	 * Last node in the chain; connect this to your destination.
	 * Points to the NR node when available, otherwise the bandpass node.
	 */
	get output(): AudioNode {
		return this._nrAvailable && this.nrNode ? this.nrNode : this.bandpassNode!;
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

		// --- Peak (peaking EQ) filter (bypassed: gain = 0) ---
		this.peakNode = ctx.createBiquadFilter();
		this.peakNode.type = 'peaking';
		this.peakNode.frequency.value = 1000;
		this.peakNode.Q.value = 1.0;
		this.peakNode.gain.value = 0;

		// --- Noise blanker (notch at 50 Hz, bypassed: Q = 0.01) ---
		this.noiseBlankerNode = ctx.createBiquadFilter();
		this.noiseBlankerNode.type = 'notch';
		this.noiseBlankerNode.frequency.value = 50;
		this.noiseBlankerNode.Q.value = 0.01;

		// --- Notch filter (bypassed: Q = 0.01) ---
		this.notchNode = ctx.createBiquadFilter();
		this.notchNode.type = 'notch';
		this.notchNode.frequency.value = 1000;
		this.notchNode.Q.value = 0.01;

		// --- Bandpass filter (bypassed: Q = 0.01 = very wide) ---
		this.bandpassNode = ctx.createBiquadFilter();
		this.bandpassNode.type = 'bandpass';
		this.bandpassNode.frequency.value = 1500;
		this.bandpassNode.Q.value = 0.01;

		// --- NR worklet (best-effort; may fail on some browsers/environments) ---
		try {
			await ctx.audioWorklet.addModule('/nr-worklet.js');
			this.nrNode = new AudioWorkletNode(ctx, 'nr-processor', {
				numberOfInputs: 1,
				numberOfOutputs: 1,
				outputChannelCount: [1],
			});
			this._nrAvailable = true;
		} catch (e) {
			console.warn('[RxDspChain] NR worklet unavailable:', e);
			this.nrNode = null;
			this._nrAvailable = false;
		}

		// Wire chain: highpass -> lowpass -> peak -> noiseBlanker -> notch -> bandpass -> [NR]
		this.highpassNode.connect(this.lowpassNode);
		this.lowpassNode.connect(this.peakNode);
		this.peakNode.connect(this.noiseBlankerNode);
		this.noiseBlankerNode.connect(this.notchNode);
		this.notchNode.connect(this.bandpassNode);
		if (this._nrAvailable && this.nrNode) {
			this.bandpassNode.connect(this.nrNode);
		}
	}

	/** Disconnect and release all nodes. */
	destroy(): void {
		this.highpassNode?.disconnect();
		this.lowpassNode?.disconnect();
		this.peakNode?.disconnect();
		this.noiseBlankerNode?.disconnect();
		this.notchNode?.disconnect();
		this.bandpassNode?.disconnect();
		this.nrNode?.disconnect();
		this.highpassNode = null;
		this.lowpassNode = null;
		this.peakNode = null;
		this.noiseBlankerNode = null;
		this.notchNode = null;
		this.bandpassNode = null;
		this.nrNode = null;
		this._nrAvailable = false;
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
	// Peak (peaking EQ) control
	// ------------------------------------------------------------------

	/** Set peak filter parameters. */
	setPeak(freqHz: number, gainDb: number, q: number): void {
		if (!this.peakNode) return;
		this.peakNode.frequency.value = freqHz;
		this.peakNode.gain.value = gainDb;
		this.peakNode.Q.value = q;
	}

	/** Enable or disable the peak filter. Bypass sets gain to 0. */
	enablePeak(enabled: boolean): void {
		if (!this.peakNode) return;
		this._peakEnabled = enabled;
		if (!enabled) {
			this.peakNode.gain.value = 0;
		}
	}

	isPeakEnabled(): boolean {
		return this._peakEnabled;
	}

	// ------------------------------------------------------------------
	// Noise blanker control
	// ------------------------------------------------------------------

	/** Set the mains-hum notch frequency (50 or 60 Hz). */
	setNoiseBlankerFreq(freq: 50 | 60): void {
		if (!this.noiseBlankerNode) return;
		this.noiseBlankerNode.frequency.value = freq;
		if (this._noiseBlankerEnabled) {
			this.noiseBlankerNode.Q.value = 30;
		}
	}

	/** Enable or disable the noise blanker. Bypass sets Q to 0.01. */
	enableNoiseBlanker(enabled: boolean): void {
		if (!this.noiseBlankerNode) return;
		this._noiseBlankerEnabled = enabled;
		this.noiseBlankerNode.Q.value = enabled ? 30 : 0.01;
	}

	isNoiseBlankerEnabled(): boolean {
		return this._noiseBlankerEnabled;
	}

	// ------------------------------------------------------------------
	// Notch filter control
	// ------------------------------------------------------------------

	/** Set notch filter centre frequency and Q. */
	setNotch(centerHz: number, q: number): void {
		if (!this.notchNode) return;
		this.notchNode.frequency.value = centerHz;
		this.notchNode.Q.value = q;
	}

	/**
	 * Set notch mode.
	 * In 'auto' mode the notch stays at 1000 Hz as a placeholder
	 * (TODO: implement automatic interference detection).
	 */
	setNotchMode(mode: 'manual' | 'auto'): void {
		this._notchMode = mode;
		if (mode === 'auto' && this.notchNode) {
			// TODO: implement automatic interference frequency detection
			this.notchNode.frequency.value = 1000;
		}
	}

	/** Enable or disable the notch filter. Bypass sets Q to 0.01. */
	enableNotch(enabled: boolean): void {
		if (!this.notchNode) return;
		this._notchEnabled = enabled;
		if (!enabled) {
			this.notchNode.Q.value = 0.01;
		}
	}

	isNotchEnabled(): boolean {
		return this._notchEnabled;
	}

	getNotchMode(): 'manual' | 'auto' {
		return this._notchMode;
	}

	// ------------------------------------------------------------------
	// Bandpass filter control
	// ------------------------------------------------------------------

	/**
	 * Apply a named bandpass preset.
	 * 'voice': center 1500 Hz, width 2400 Hz (Q ≈ 0.625)
	 * 'cw':    center 700 Hz,  width 500 Hz  (Q = 1.4)
	 * 'manual': no-op — caller must call setBandpass() explicitly.
	 */
	setBandpassPreset(preset: 'voice' | 'cw' | 'manual'): void {
		this._bandpassPreset = preset;
		if (preset !== 'manual') {
			const { centerHz, widthHz } = BANDPASS_PRESETS[preset];
			this.setBandpass(centerHz, widthHz);
		}
	}

	/** Set bandpass centre frequency and -3 dB bandwidth (Hz). */
	setBandpass(centerHz: number, widthHz: number): void {
		if (!this.bandpassNode) return;
		this.bandpassNode.frequency.value = centerHz;
		this.bandpassNode.Q.value = widthHz > 0 ? centerHz / widthHz : 1;
	}

	/** Enable or disable the bandpass filter. Bypass sets Q to 0.01. */
	enableBandpass(enabled: boolean): void {
		if (!this.bandpassNode) return;
		this._bandpassEnabled = enabled;
		if (!enabled) {
			this.bandpassNode.Q.value = 0.01;
		}
	}

	isBandpassEnabled(): boolean {
		return this._bandpassEnabled;
	}

	getBandpassPreset(): 'voice' | 'cw' | 'manual' {
		return this._bandpassPreset;
	}

	// ------------------------------------------------------------------
	// Noise reduction (AudioWorklet) control
	// ------------------------------------------------------------------

	/** Set NR reduction amount (0.0 = off, 1.0 = maximum). */
	setNrAmount(amount: number): void {
		if (!this.nrNode) return;
		const param = this.nrNode.parameters.get('amount');
		if (param) param.value = Math.max(0, Math.min(1, amount));
	}

	/** Enable or disable the NR worklet. No-op if worklet is unavailable. */
	enableNr(enabled: boolean): void {
		if (!this.nrNode) return;
		this._nrEnabled = enabled;
		const param = this.nrNode.parameters.get('enabled');
		if (param) param.value = enabled ? 1 : 0;
	}

	isNrEnabled(): boolean {
		return this._nrEnabled;
	}

	isNrAvailable(): boolean {
		return this._nrAvailable;
	}
}
