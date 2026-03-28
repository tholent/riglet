/**
 * VoxDetector — voice-operated transmit detector.
 *
 * Computes the RMS of each incoming PCM block and compares to a configurable
 * threshold.  Implements two protection mechanisms:
 *
 *  - Anti-vox delay: the input must exceed the threshold continuously for
 *    `antiVoxDelayMs` before the first trigger fires.  This prevents a single
 *    transient (e.g. keyboard click) from keying the transmitter.
 *
 *  - Hang time: once triggered, the detector stays active for `hangTimeMs`
 *    after the last above-threshold block.  This prevents PTT chatter between
 *    words.
 *
 * Usage:
 *   const vox = new VoxDetector({ thresholdDb: -40, hangTimeMs: 500, antiVoxDelayMs: 50 });
 *   // call process() for every PCM chunk fed from the microphone
 *   const pttActive = vox.process(float32Block);
 */

export interface VoxParams {
	/** Threshold level in dBFS.  Blocks whose RMS is above this activate VOX. */
	thresholdDb: number;
	/** How long (ms) to keep VOX active after the last above-threshold block. */
	hangTimeMs: number;
	/** How long (ms) the signal must continuously exceed threshold before the
	 *  first trigger.  Prevents single-transient false triggers. */
	antiVoxDelayMs: number;
}

const SAMPLE_RATE = 16000; // PCM chunks are 16 kHz mono s16le

export class VoxDetector {
	private thresholdDb: number;
	private hangTimeMs: number;
	private antiVoxDelayMs: number;

	// Timestamp (ms) of the last above-threshold block
	private lastAboveMs = -Infinity;
	// Timestamp (ms) of when continuous above-threshold signal started
	private continuousAboveSince = -Infinity;
	// Whether VOX is currently active (i.e. PTT should be on)
	private active = false;

	constructor(params: VoxParams) {
		this.thresholdDb = params.thresholdDb;
		this.hangTimeMs = params.hangTimeMs;
		this.antiVoxDelayMs = params.antiVoxDelayMs;
	}

	/**
	 * Process one block of normalised Float32 PCM samples.
	 * Returns true while voice is detected (PTT should be active).
	 */
	process(pcm: Float32Array): boolean {
		const rms = computeRms(pcm);
		const rmsDb = rms > 0 ? 20 * Math.log10(rms) : -Infinity;
		const nowMs = performance.now();
		const blockDurationMs = (pcm.length / SAMPLE_RATE) * 1000;

		if (rmsDb >= this.thresholdDb) {
			// Signal is above threshold this block
			if (this.continuousAboveSince === -Infinity) {
				// First block above threshold — start the anti-vox timer
				this.continuousAboveSince = nowMs;
			}
			this.lastAboveMs = nowMs + blockDurationMs;

			const continuousMs = nowMs - this.continuousAboveSince;
			if (continuousMs >= this.antiVoxDelayMs) {
				// Anti-vox delay satisfied — activate
				this.active = true;
			}
		} else {
			// Signal is below threshold — reset continuous-above tracker
			this.continuousAboveSince = -Infinity;

			if (this.active) {
				// Check hang time: stay active until hang time elapses
				if (nowMs > this.lastAboveMs + this.hangTimeMs) {
					this.active = false;
				}
			}
		}

		return this.active;
	}

	/** Reset all state (e.g. when VOX is toggled off). */
	reset(): void {
		this.active = false;
		this.lastAboveMs = -Infinity;
		this.continuousAboveSince = -Infinity;
	}
}

function computeRms(pcm: Float32Array): number {
	if (pcm.length === 0) return 0;
	let sum = 0;
	for (let i = 0; i < pcm.length; i++) {
		sum += pcm[i] * pcm[i];
	}
	return Math.sqrt(sum / pcm.length);
}
