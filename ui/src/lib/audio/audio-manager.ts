/**
 * AudioManager creates and manages the Web Audio API context,
 * the PcmWorkletProcessor AudioWorklet node, microphone capture,
 * and speaker output for one radio.
 *
 * Integration:
 *   - Call feedRx(buffer) from the audio WebSocket binary message handler.
 *   - Set onTxChunk callback to forward captured TX audio to the WebSocket.
 */

export class AudioManager {
	private audioCtx: AudioContext | null = null;
	private workletNode: AudioWorkletNode | null = null;
	private gainNode: GainNode | null = null;
	private micStream: MediaStream | null = null;
	private micSource: MediaStreamAudioSourceNode | null = null;
	private txActive = false;
	private volume = 0.5;

	/** Called with s16le PCM ArrayBuffer for each TX chunk captured from mic */
	onTxChunk: ((buffer: ArrayBuffer) => void) | null = null;

	async startRx(): Promise<void> {
		if (this.audioCtx) return; // already running

		this.audioCtx = new AudioContext({ sampleRate: 16000 });
		this.gainNode = this.audioCtx.createGain();
		this.gainNode.gain.value = this.volume;

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

		this.workletNode.connect(this.gainNode);
		this.gainNode.connect(this.audioCtx.destination);
	}

	stopRx(): void {
		this.gainNode?.disconnect();
		this.workletNode?.disconnect();
		this.audioCtx?.close().catch(() => undefined);
		this.audioCtx = null;
		this.workletNode = null;
		this.gainNode = null;
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

	/** Feed a received s16le PCM ArrayBuffer from the server into the RX ring buffer */
	feedRx(buffer: ArrayBuffer): void {
		if (!this.workletNode) return;
		// Transfer ownership to worklet to avoid copy
		this.workletNode.port.postMessage({ type: 'rx', payload: buffer }, [buffer]);
	}

	setVolume(v: number): void {
		this.volume = Math.max(0, Math.min(1, v));
		if (this.gainNode) {
			this.gainNode.gain.value = this.volume;
		}
	}
}
