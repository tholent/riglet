/**
 * AudioManager creates and manages the Web Audio API context,
 * the PcmWorkletProcessor AudioWorklet node, microphone capture,
 * and speaker output for one radio.
 *
 * DSP chain (RX path):
 *   workletNode -> squelchGate -> volumeGain -> destination
 *
 * The squelch gate is implemented as a gain node whose value is snapped
 * to 0 (closed) or 1 (open) based on the RMS level of incoming PCM chunks
 * relative to the squelch threshold.  A simple hold timer prevents rapid
 * open/close chatter.
 *
 * Integration:
 *   - Call feedRx(buffer) from the audio WebSocket binary message handler.
 *   - Set onTxChunk callback to forward captured TX audio to the WebSocket.
 */

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

	private micStream: MediaStream | null = null;
	private micSource: MediaStreamAudioSourceNode | null = null;
	private txActive = false;
	private volume = 0.5;

	// Squelch state
	private squelch: SquelchParams = { ...DEFAULT_SQUELCH };
	private squelchOpen = true;
	private squelchHoldTimer: ReturnType<typeof setTimeout> | null = null;

	/** Called with s16le PCM ArrayBuffer for each TX chunk captured from mic */
	onTxChunk: ((buffer: ArrayBuffer) => void) | null = null;

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
			}
		};

		// Wire up DSP chain: worklet -> squelch -> volume -> speakers
		this.workletNode.connect(this.squelchNode);
		this.squelchNode.connect(this.gainNode);
		this.gainNode.connect(this.audioCtx.destination);
	}

	stopRx(): void {
		if (this.squelchHoldTimer !== null) {
			clearTimeout(this.squelchHoldTimer);
			this.squelchHoldTimer = null;
		}
		this.gainNode?.disconnect();
		this.squelchNode?.disconnect();
		this.workletNode?.disconnect();
		this.audioCtx?.close().catch(() => undefined);
		this.audioCtx = null;
		this.workletNode = null;
		this.gainNode = null;
		this.squelchNode = null;
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
