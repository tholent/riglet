/**
 * TxDspChain — client-side audio DSP processing chain for the TX path.
 *
 * Current chain (Wave 1):
 *   highpass -> lowpass
 *
 * Additional stages (EQ, compressor, limiter, gate) are added in Wave 2.
 *
 * All stages are bypassed by default (pass-through). Build with build() before use.
 *
 * Usage:
 *   const chain = new TxDspChain(audioCtx);
 *   await chain.build();
 *   micSource.connect(chain.input);
 *   chain.output.connect(workletNode);
 */

export class TxDspChain {
	private ctx: AudioContext;
	private highpassNode: BiquadFilterNode | null = null;
	private lowpassNode: BiquadFilterNode | null = null;

	// Enabled state
	private _highpassEnabled = false;
	private _lowpassEnabled = false;

	constructor(ctx: AudioContext) {
		this.ctx = ctx;
	}

	/** First node in the chain; connect your microphone source here. */
	get input(): AudioNode {
		return this.highpassNode!;
	}

	/** Last node in the chain; connect this to the PCM worklet or destination. */
	get output(): AudioNode {
		return this.lowpassNode!;
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

		// Wire chain: highpass -> lowpass
		this.highpassNode.connect(this.lowpassNode);
	}

	/** Disconnect and release all nodes. */
	destroy(): void {
		this.highpassNode?.disconnect();
		this.lowpassNode?.disconnect();
		this.highpassNode = null;
		this.lowpassNode = null;
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
}
