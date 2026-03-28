/**
 * DspChain — client-side audio DSP processing chain for the RX path.
 *
 * Chain order (all nodes created on the same AudioContext):
 *
 *   worklet → bandpass → notch → NR → compressor → bass → mid → treble → squelch → gain → destination
 *
 * All filter stages are bypassed by default (pass-through).
 *
 * Usage:
 *   const chain = new DspChain(audioCtx);
 *   await chain.build();
 *   workletNode.connect(chain.input);
 *   chain.output.connect(squelchNode); // or destination
 *
 *   chain.setBandpass(1500, 300);
 *   chain.enableBandpass(true);
 */

export interface CompressorParams {
	threshold: number; // dBFS, default -24
	ratio: number; // default 4
	attack: number; // seconds, default 0.003
	release: number; // seconds, default 0.25
}

const DEFAULT_COMPRESSOR: CompressorParams = {
	threshold: -24,
	ratio: 4,
	attack: 0.003,
	release: 0.25,
};

export class DspChain {
	// Filter nodes (public for direct Web Audio API inspection if needed)
	bandpassNode: BiquadFilterNode | null = null;
	notchNode: BiquadFilterNode | null = null;
	nrNode: AudioWorkletNode | null = null;
	compressorNode: DynamicsCompressorNode | null = null;
	bassNode: BiquadFilterNode | null = null;
	midNode: BiquadFilterNode | null = null;
	trebleNode: BiquadFilterNode | null = null;

	// Bypass state flags
	private _bandpassEnabled = false;
	private _notchEnabled = false;
	private _nrEnabled = false;
	private _compressorEnabled = false;
	private _eqEnabled = false;

	// Whether NR worklet has been successfully loaded
	private _nrAvailable = false;

	private _ctx: AudioContext;

	/** The first node in the chain; connect your worklet output here. */
	get input(): AudioNode {
		return this.bandpassNode!;
	}

	/** The last node in the chain; connect this to your squelch/gain node. */
	get output(): AudioNode {
		return this.trebleNode!;
	}

	constructor(ctx: AudioContext) {
		this._ctx = ctx;
	}

	/**
	 * Allocate and wire all DSP nodes.
	 * Must be called once after construction, before connecting to the graph.
	 * Returns a Promise because loading the NR worklet is async (best-effort).
	 */
	async build(): Promise<void> {
		const ctx = this._ctx;

		// Bandpass filter (bypassed by default: wide pass so it's transparent)
		this.bandpassNode = ctx.createBiquadFilter();
		this.bandpassNode.type = 'bandpass';
		this.bandpassNode.frequency.value = 1500;
		this.bandpassNode.Q.value = 0.01; // very wide = effectively off

		// Notch filter (bypassed by default: Q very low = no notch)
		this.notchNode = ctx.createBiquadFilter();
		this.notchNode.type = 'notch';
		this.notchNode.frequency.value = 1000;
		this.notchNode.Q.value = 0.01;

		// Noise reduction worklet (best-effort: may fail on some browsers)
		try {
			await ctx.audioWorklet.addModule('/nr-worklet.js');
			this.nrNode = new AudioWorkletNode(ctx, 'nr-processor', {
				numberOfInputs: 1,
				numberOfOutputs: 1,
				outputChannelCount: [1],
			});
			this._nrAvailable = true;
		} catch (e) {
			console.warn('[DspChain] NR worklet unavailable:', e);
			this.nrNode = null;
			this._nrAvailable = false;
		}

		// Dynamics compressor
		this.compressorNode = ctx.createDynamicsCompressor();
		this.compressorNode.threshold.value = DEFAULT_COMPRESSOR.threshold;
		this.compressorNode.ratio.value = DEFAULT_COMPRESSOR.ratio;
		this.compressorNode.attack.value = DEFAULT_COMPRESSOR.attack;
		this.compressorNode.release.value = DEFAULT_COMPRESSOR.release;
		this.compressorNode.knee.value = 6;

		// Bass shelf (lowshelf, default 0 dB gain = transparent)
		this.bassNode = ctx.createBiquadFilter();
		this.bassNode.type = 'lowshelf';
		this.bassNode.frequency.value = 200;
		this.bassNode.gain.value = 0;

		// Mid peaking EQ (default 0 dB = transparent)
		this.midNode = ctx.createBiquadFilter();
		this.midNode.type = 'peaking';
		this.midNode.frequency.value = 1000;
		this.midNode.Q.value = 1.0;
		this.midNode.gain.value = 0;

		// Treble shelf (highshelf, default 0 dB = transparent)
		this.trebleNode = ctx.createBiquadFilter();
		this.trebleNode.type = 'highshelf';
		this.trebleNode.frequency.value = 3000;
		this.trebleNode.gain.value = 0;

		// Wire chain in series: bandpass → notch → [NR] → compressor → bass → mid → treble
		if (this.nrNode) {
			this.bandpassNode.connect(this.notchNode);
			this.notchNode.connect(this.nrNode);
			this.nrNode.connect(this.compressorNode);
		} else {
			this.bandpassNode.connect(this.notchNode);
			this.notchNode.connect(this.compressorNode);
		}
		this.compressorNode.connect(this.bassNode);
		this.bassNode.connect(this.midNode);
		this.midNode.connect(this.trebleNode);
	}

	/** Release all nodes (call when AudioContext is closing). */
	destroy(): void {
		this.bandpassNode?.disconnect();
		this.notchNode?.disconnect();
		this.nrNode?.disconnect();
		this.compressorNode?.disconnect();
		this.bassNode?.disconnect();
		this.midNode?.disconnect();
		this.trebleNode?.disconnect();
		this.bandpassNode = null;
		this.notchNode = null;
		this.nrNode = null;
		this.compressorNode = null;
		this.bassNode = null;
		this.midNode = null;
		this.trebleNode = null;
	}

	// ------------------------------------------------------------------
	// Bandpass control
	// ------------------------------------------------------------------

	/**
	 * Set bandpass filter parameters.
	 * @param centerHz  Centre frequency in Hz
	 * @param widthHz   -3 dB bandwidth in Hz (converted to Q internally)
	 */
	setBandpass(centerHz: number, widthHz: number): void {
		if (!this.bandpassNode) return;
		this.bandpassNode.frequency.value = centerHz;
		// Q = centerHz / widthHz for a bandpass filter
		this.bandpassNode.Q.value = widthHz > 0 ? centerHz / widthHz : 1;
	}

	enableBandpass(enabled: boolean): void {
		if (!this.bandpassNode) return;
		this._bandpassEnabled = enabled;
		if (!enabled) {
			// Wide-open pass — effectively transparent
			this.bandpassNode.Q.value = 0.01;
		}
	}

	isBandpassEnabled(): boolean {
		return this._bandpassEnabled;
	}

	// ------------------------------------------------------------------
	// Notch control
	// ------------------------------------------------------------------

	/**
	 * Set notch filter parameters.
	 * @param centerHz  Notch centre frequency in Hz
	 * @param widthHz   -3 dB notch width in Hz (converted to Q)
	 */
	setNotch(centerHz: number, widthHz: number): void {
		if (!this.notchNode) return;
		this.notchNode.frequency.value = centerHz;
		this.notchNode.Q.value = widthHz > 0 ? centerHz / widthHz : 30;
	}

	enableNotch(enabled: boolean): void {
		if (!this.notchNode) return;
		this._notchEnabled = enabled;
		if (!enabled) {
			// Near-zero Q = no notch effect
			this.notchNode.Q.value = 0.01;
		}
	}

	isNotchEnabled(): boolean {
		return this._notchEnabled;
	}

	// ------------------------------------------------------------------
	// Noise reduction control
	// ------------------------------------------------------------------

	/** Set NR amount (0.0 = off, 1.0 = maximum). */
	setNrAmount(amount: number): void {
		if (!this.nrNode) return;
		const param = this.nrNode.parameters.get('amount');
		if (param) param.value = Math.max(0, Math.min(1, amount));
	}

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

	// ------------------------------------------------------------------
	// Compressor control
	// ------------------------------------------------------------------

	/**
	 * Configure the dynamics compressor.
	 * @param threshold  dBFS threshold (-100..0)
	 * @param ratio      Compression ratio (1..20)
	 * @param attack     Attack time in seconds
	 * @param release    Release time in seconds
	 */
	setCompressor(threshold: number, ratio: number, attack: number, release: number): void {
		if (!this.compressorNode) return;
		this.compressorNode.threshold.value = Math.max(-100, Math.min(0, threshold));
		this.compressorNode.ratio.value = Math.max(1, Math.min(20, ratio));
		this.compressorNode.attack.value = Math.max(0, attack);
		this.compressorNode.release.value = Math.max(0, release);
	}

	enableCompressor(enabled: boolean): void {
		if (!this.compressorNode) return;
		this._compressorEnabled = enabled;
		if (!enabled) {
			// Set ratio to 1:1 — compressor has no effect
			this.compressorNode.ratio.value = 1;
			this.compressorNode.threshold.value = 0;
		}
	}

	isCompressorEnabled(): boolean {
		return this._compressorEnabled;
	}

	// ------------------------------------------------------------------
	// 3-band EQ control
	// ------------------------------------------------------------------

	/** Set bass shelf gain in dB. Range: [-40, +40]. */
	setBass(gainDb: number): void {
		if (!this.bassNode) return;
		this.bassNode.gain.value = Math.max(-40, Math.min(40, gainDb));
	}

	/** Set mid peaking gain in dB. Range: [-40, +40]. */
	setMid(gainDb: number): void {
		if (!this.midNode) return;
		this.midNode.gain.value = Math.max(-40, Math.min(40, gainDb));
	}

	/** Set treble shelf gain in dB. Range: [-40, +40]. */
	setTreble(gainDb: number): void {
		if (!this.trebleNode) return;
		this.trebleNode.gain.value = Math.max(-40, Math.min(40, gainDb));
	}

	enableEq(enabled: boolean): void {
		this._eqEnabled = enabled;
		if (!enabled) {
			// Zero all EQ gains — transparent pass-through
			if (this.bassNode) this.bassNode.gain.value = 0;
			if (this.midNode) this.midNode.gain.value = 0;
			if (this.trebleNode) this.trebleNode.gain.value = 0;
		}
	}

	isEqEnabled(): boolean {
		return this._eqEnabled;
	}
}
