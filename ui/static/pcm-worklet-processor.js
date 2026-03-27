/**
 * PCM AudioWorklet processor for Riglet.
 *
 * RX path: Receives s16le PCM chunks via MessagePort, converts to Float32,
 *          writes into a ring buffer, and outputs to the audio graph.
 *
 * TX path: Captures Float32 input from the audio graph (mic),
 *          converts to s16le, sends back via MessagePort.
 *
 * Ring buffer: 5 chunks deep (100ms @ 20ms/chunk) to absorb network jitter.
 */

const CHUNK_SAMPLES = 320; // 20ms @ 16kHz
const RING_CHUNKS = 5;
const RING_SIZE = CHUNK_SAMPLES * RING_CHUNKS;

class PcmWorkletProcessor extends AudioWorkletProcessor {
	constructor() {
		super();
		// RX ring buffer (Float32)
		this._rxBuf = new Float32Array(RING_SIZE);
		this._rxWrite = 0;
		this._rxRead = 0;
		this._rxAvail = 0;

		this.port.onmessage = (event) => {
			const { type, payload } = event.data;
			if (type === 'rx') {
				// payload is an ArrayBuffer containing s16le PCM
				const s16 = new Int16Array(payload);
				for (let i = 0; i < s16.length; i++) {
					if (this._rxAvail < RING_SIZE) {
						this._rxBuf[this._rxWrite] = s16[i] / 32768.0;
						this._rxWrite = (this._rxWrite + 1) % RING_SIZE;
						this._rxAvail++;
					}
					// Drop samples if ring is full (back-pressure)
				}
			}
		};
	}

	process(inputs, outputs) {
		// RX: fill output channel from ring buffer
		const outChannel = outputs[0]?.[0];
		if (outChannel) {
			for (let i = 0; i < outChannel.length; i++) {
				if (this._rxAvail > 0) {
					outChannel[i] = this._rxBuf[this._rxRead];
					this._rxRead = (this._rxRead + 1) % RING_SIZE;
					this._rxAvail--;
				} else {
					outChannel[i] = 0; // underrun silence
				}
			}
		}

		// TX: capture from first input channel and send as s16le
		const inChannel = inputs[0]?.[0];
		if (inChannel && inChannel.length > 0) {
			const s16 = new Int16Array(inChannel.length);
			for (let i = 0; i < inChannel.length; i++) {
				const clamped = Math.max(-1, Math.min(1, inChannel[i]));
				s16[i] = Math.round(clamped * 32767);
			}
			this.port.postMessage({ type: 'tx', payload: s16.buffer }, [s16.buffer]);
		}

		return true; // keep processor alive
	}
}

registerProcessor('pcm-worklet-processor', PcmWorkletProcessor);
