/**
 * AudioManager creates and manages the Web Audio API context,
 * the PcmWorkletProcessor AudioWorklet node, microphone capture,
 * and speaker output for one radio.
 *
 * DSP chain (RX path):
 *   workletNode -> bandpass -> notch -> compressor -> bass -> mid -> treble -> squelchGate -> volumeGain -> destination
 *
 * The squelch gate is implemented as a gain node whose value is snapped
 * to 0 (closed) or 1 (open) based on the RMS level of incoming PCM chunks
 * relative to the squelch threshold.  A simple hold timer prevents rapid
 * open/close chatter.
 *
 * All DSP filter/EQ/compressor nodes are managed by DspChain and are
 * bypassed by default.
 *
 * Integration:
 *   - Call feedRx(buffer) from the audio WebSocket binary message handler.
 *   - Set onTxChunk callback to forward captured TX audio to the WebSocket.
 */

import { DspChain } from './dsp-chain.js';

/** Configuration for the squelch audio gate. */
export interface SquelchParams {
	/** RMS threshold in the range 0..1.  0 = squelch fully open (no gate). */
	threshold: number;
	/** Milliseconds to hold the gate open after signal drops below threshold. */
	holdMs: number;
}

const DEFAULT_SQUELCH: SquelchParams = { threshold: 0, holdMs: 200 };

export class AudioManager {
	private audioCtx: AudioContext | null = null;
	private workletNode: AudioWorkletNode | null = null;

	// Volume (output level) gain node
	private gainNode: GainNode | null = null;

	// Squelch gate gain node (0 = muted, 1 = open)
	private squelchNode: GainNode | null = null;

	// DSP filter/EQ/compressor chain
	private dspChain: DspChain | null = null;

	private micStream: MediaStream | null = null;
	private micSource: MediaStreamAudioSourceNode | null = null;
	private txActive = false;
	private volume = 0.5;

	// Mic-as-RX (simulation mode)
	private micRxStream: MediaStream | null = null;
	private micRxSource: MediaStreamAudioSourceNode | null = null;
	private micRxAnalyser: AnalyserNode | null = null;
	private micRxFftAnalyser: AnalyserNode | null = null;
	private micRxRaf = 0;

	/** Called with FFT magnitude bins (Float32, dBFS) for spectrum/waterfall when in simulation mode. */
	onSimFftBins: ((bins: Float32Array) => void) | null = null;

	// Squelch state
	private squelch: SquelchParams = { ...DEFAULT_SQUELCH };
	private squelchOpen = true;
	private squelchHoldTimer: ReturnType<typeof setTimeout> | null = null;

	/** Called with s16le PCM ArrayBuffer for each TX chunk captured from mic */
	onTxChunk: ((buffer: ArrayBuffer) => void) | null = null;

	/** Called with Float32Array of TX PCM for visualization (normalised -1..+1). */
	onTxPcmFloat: ((samples: Float32Array) => void) | null = null;

	/** Called with Float32Array of RX PCM for visualization (normalised -1..+1). */
	onRxPcmFloat: ((samples: Float32Array) => void) | null = null;

	async startRx(): Promise<void> {
		if (this.audioCtx) return; // already running

		this.audioCtx = new AudioContext({ sampleRate: 16000 });

		// Volume gain node (user-controlled output level)
		this.gainNode = this.audioCtx.createGain();
		this.gainNode.gain.value = this.volume;

		// Squelch gate node (0 = muted, 1 = pass)
		this.squelchNode = this.audioCtx.createGain();
		this.squelchNode.gain.value = this.squelch.threshold === 0 ? 1 : 0;

		// The worklet processor JS is copied to /audio/ by Vite at build time.
		// In development the file is served from $lib/audio/.
		await this.audioCtx.audioWorklet.addModule('/pcm-worklet-processor.js');

		this.workletNode = new AudioWorkletNode(this.audioCtx, 'pcm-worklet-processor', {
			numberOfInputs: 1,
			numberOfOutputs: 1,
			outputChannelCount: [1],
		});

		this.workletNode.port.onmessage = (event: MessageEvent) => {
			const { type, payload } = event.data as { type: string; payload: ArrayBuffer };
			if (type === 'tx' && this.txActive && this.onTxChunk) {
				this.onTxChunk(payload);
				if (this.onTxPcmFloat) {
					this.onTxPcmFloat(_s16leToFloat32(payload));
				}
			} else if (type === 'rx-float' && this.onRxPcmFloat) {
				this.onRxPcmFloat(payload as unknown as Float32Array);
			}
		};

		// Build DSP filter/EQ/compressor chain (async to load NR worklet)
		this.dspChain = new DspChain(this.audioCtx);
		await this.dspChain.build();

		// Wire up full DSP chain:
		// worklet -> bandpass -> notch -> compressor -> bass -> mid -> treble -> squelch -> volume -> speakers
		this.workletNode.connect(this.dspChain.input);
		this.dspChain.output.connect(this.squelchNode);
		this.squelchNode.connect(this.gainNode);
		this.gainNode.connect(this.audioCtx.destination);
	}

	/**
	 * Simulation mode: capture the client microphone and route it through the
	 * RX DSP chain so it plays through speakers and drives all visualizations.
	 * Fires onRxPcmFloat at ~60 fps for LUFS metering and viz.
	 */
	async startMicAsRx(): Promise<void> {
		if (!this.audioCtx || !this.dspChain) return;
		try {
			this.micRxStream = await navigator.mediaDevices.getUserMedia({
				audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true },
				video: false,
			});
			this.micRxSource = this.audioCtx.createMediaStreamSource(this.micRxStream);
			// Feed mic through the DSP chain → squelch → volume → speakers
			this.micRxSource.connect(this.dspChain.input);

			// Resume the AudioContext — it starts suspended in most browsers
			// until a user gesture.  The getUserMedia permission prompt qualifies.
			await this.audioCtx.resume();

			// Time-domain tap for onRxPcmFloat (LUFS / PCM-based visualizations)
			this.micRxAnalyser = this.audioCtx.createAnalyser();
			this.micRxAnalyser.fftSize = 512;
			this.micRxSource.connect(this.micRxAnalyser);

			// Frequency-domain tap for onSimFftBins (spectrum strip / waterfall)
			this.micRxFftAnalyser = this.audioCtx.createAnalyser();
			this.micRxFftAnalyser.fftSize = 2048;
			this.micRxFftAnalyser.smoothingTimeConstant = 0.75;
			this.micRxSource.connect(this.micRxFftAnalyser);

			const poll = () => {
				// Allocate fresh buffers every frame — Svelte $state uses strict
				// equality (===) to detect changes, so reusing the same reference
				// would silently suppress all reactive updates.
				const pcmFrame = new Float32Array(this.micRxAnalyser!.fftSize);
				this.micRxAnalyser!.getFloatTimeDomainData(pcmFrame);
				this.onRxPcmFloat?.(pcmFrame);

				if (this.onSimFftBins) {
					const fftFrame = new Float32Array(this.micRxFftAnalyser!.frequencyBinCount);
					this.micRxFftAnalyser!.getFloatFrequencyData(fftFrame);
					this.onSimFftBins(fftFrame);
				}

				this.micRxRaf = requestAnimationFrame(poll);
			};
			this.micRxRaf = requestAnimationFrame(poll);
		} catch (e) {
			console.warn('[AudioManager] Mic access for simulation RX denied:', e);
		}
	}

	stopMicAsRx(): void {
		cancelAnimationFrame(this.micRxRaf);
		this.micRxAnalyser?.disconnect();
		this.micRxAnalyser = null;
		this.micRxFftAnalyser?.disconnect();
		this.micRxFftAnalyser = null;
		this.micRxSource?.disconnect();
		this.micRxSource = null;
		this.micRxStream?.getTracks().forEach((t) => t.stop());
		this.micRxStream = null;
	}

	stopRx(): void {
		this.stopMicAsRx();
		if (this.squelchHoldTimer !== null) {
			clearTimeout(this.squelchHoldTimer);
			this.squelchHoldTimer = null;
		}
		this.dspChain?.destroy();
		this.dspChain = null;
		this.gainNode?.disconnect();
		this.squelchNode?.disconnect();
		this.workletNode?.disconnect();
		this.audioCtx?.close().catch(() => undefined);
		this.audioCtx = null;
		this.workletNode = null;
		this.gainNode = null;
		this.squelchNode = null;
	}

	// ------------------------------------------------------------------
	// DSP chain access
	// ------------------------------------------------------------------

	/** Returns the DSP chain for filter/EQ/compressor control.
	 *  Returns null if RX is not started yet. */
	getDspChain(): DspChain | null {
		return this.dspChain;
	}

	async startTx(): Promise<void> {
		if (!this.audioCtx || !this.workletNode) return;
		try {
			this.micStream = await navigator.mediaDevices.getUserMedia({
				audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true },
				video: false,
			});
			this.micSource = this.audioCtx.createMediaStreamSource(this.micStream);
			this.micSource.connect(this.workletNode);
			this.txActive = true;
		} catch (e) {
			console.warn('Mic access denied or unavailable:', e);
		}
	}

	stopTx(): void {
		this.txActive = false;
		this.micSource?.disconnect();
		this.micSource = null;
		this.micStream?.getTracks().forEach((t) => t.stop());
		this.micStream = null;
	}

	/** Feed a received s16le PCM ArrayBuffer from the server into the RX ring buffer.
	 *  Also evaluates squelch based on RMS of the incoming chunk. */
	feedRx(buffer: ArrayBuffer): void {
		if (!this.workletNode) return;

		// Notify RX PCM visualization listeners before we transfer the buffer
		if (this.onRxPcmFloat) {
			this.onRxPcmFloat(_s16leToFloat32(buffer));
		}

		// Evaluate squelch if threshold > 0
		if (this.squelch.threshold > 0) {
			this._evaluateSquelch(buffer);
		} else if (!this.squelchOpen) {
			// Threshold was set to 0 (disabled) — ensure gate is open
			this._openGate();
		}

		// Transfer ownership to worklet to avoid copy
		this.workletNode.port.postMessage({ type: 'rx', payload: buffer }, [buffer]);
	}

	// ------------------------------------------------------------------
	// Volume control
	// ------------------------------------------------------------------

	/** Set output volume. v in range [0, 1]. */
	setVolume(v: number): void {
		this.volume = Math.max(0, Math.min(1, v));
		if (this.gainNode) {
			this.gainNode.gain.value = this.volume;
		}
	}

	getVolume(): number {
		return this.volume;
	}

	// ------------------------------------------------------------------
	// Squelch control
	// ------------------------------------------------------------------

	/** Configure the squelch gate.
	 *  threshold=0 disables squelch (gate always open).
	 *  threshold=1 only passes very loud signals. */
	setSquelch(params: Partial<SquelchParams>): void {
		this.squelch = { ...this.squelch, ...params };

		if (this.squelch.threshold === 0) {
			// Squelch disabled — open gate immediately
			this._openGate();
		}
	}

	getSquelch(): SquelchParams {
		return { ...this.squelch };
	}

	isSquelchOpen(): boolean {
		return this.squelchOpen;
	}

	// ------------------------------------------------------------------
	// Private helpers
	// ------------------------------------------------------------------

	private _evaluateSquelch(buffer: ArrayBuffer): void {
		const rms = _computeRms(buffer);
		if (rms >= this.squelch.threshold) {
			// Signal above threshold — open gate and reset hold timer
			if (this.squelchHoldTimer !== null) {
				clearTimeout(this.squelchHoldTimer);
				this.squelchHoldTimer = null;
			}
			this._openGate();
		} else {
			// Signal below threshold — start hold timer if not already running
			if (this.squelchOpen && this.squelchHoldTimer === null) {
				this.squelchHoldTimer = setTimeout(() => {
					this.squelchHoldTimer = null;
					this._closeGate();
				}, this.squelch.holdMs);
			}
		}
	}

	private _openGate(): void {
		this.squelchOpen = true;
		if (this.squelchNode) {
			this.squelchNode.gain.value = 1;
		}
	}

	private _closeGate(): void {
		this.squelchOpen = false;
		if (this.squelchNode) {
			this.squelchNode.gain.value = 0;
		}
	}
}

/** Convert s16le PCM ArrayBuffer to Float32Array normalised to [-1, +1]. */
function _s16leToFloat32(buffer: ArrayBuffer): Float32Array {
	const ints = new Int16Array(buffer);
	const floats = new Float32Array(ints.length);
	for (let i = 0; i < ints.length; i++) {
		floats[i] = ints[i] / 32768;
	}
	return floats;
}

/** Compute the RMS amplitude of an s16le PCM buffer, normalised to [0, 1]. */
function _computeRms(buffer: ArrayBuffer): number {
	const samples = new Int16Array(buffer);
	if (samples.length === 0) return 0;
	let sumSq = 0;
	for (let i = 0; i < samples.length; i++) {
		const norm = samples[i] / 32768;
		sumSq += norm * norm;
	}
	return Math.sqrt(sumSq / samples.length);
}
