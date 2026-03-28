/**
 * LUFS measurement per ITU-R BS.1770-4.
 *
 * Implements:
 *  - K-weighting filter (two biquad stages at 16 kHz sample rate)
 *  - Momentary loudness (400 ms window)
 *  - Short-term loudness (3 s window)
 *
 * Usage:
 *   const meter = new LufsMeter(16000);
 *   meter.process(float32Chunk);   // feed PCM frames
 *   const db = meter.getMomentary();
 */

const NEG_INF_LUFS = -144;

/** 2nd-order IIR biquad filter (Direct Form I). */
class Biquad {
	private b0: number;
	private b1: number;
	private b2: number;
	private a1: number;
	private a2: number;
	private x1 = 0;
	private x2 = 0;
	private y1 = 0;
	private y2 = 0;

	constructor(b0: number, b1: number, b2: number, a1: number, a2: number) {
		this.b0 = b0;
		this.b1 = b1;
		this.b2 = b2;
		this.a1 = a1;
		this.a2 = a2;
	}

	process(x: number): number {
		const y =
			this.b0 * x +
			this.b1 * this.x1 +
			this.b2 * this.x2 -
			this.a1 * this.y1 -
			this.a2 * this.y2;
		this.x2 = this.x1;
		this.x1 = x;
		this.y2 = this.y1;
		this.y1 = y;
		return y;
	}

	reset(): void {
		this.x1 = this.x2 = this.y1 = this.y2 = 0;
	}
}

/** Build K-weighting pre-filter (stage 1: high-shelf) for 16 kHz. */
function makePreFilter(): Biquad {
	// Coefficients pre-calculated for fs=16000 Hz per ITU-R BS.1770 Annex 1.
	// Stage 1: High-shelf +4 dB at ~1681 Hz
	return new Biquad(1.53512485958697, -2.69169618940638, 1.19839281085285, -1.69065929318241, 0.73248077421585);
}

/** Build K-weighting RLB filter (stage 2: high-pass) for 16 kHz. */
function makeRlbFilter(): Biquad {
	// Stage 2: High-pass at ~38 Hz
	return new Biquad(1.0, -2.0, 1.0, -1.99004745483398, 0.99007225036603);
}

export class LufsMeter {
	private sampleRate: number;

	// K-weighting filters
	private preFilter: Biquad;
	private rlbFilter: Biquad;

	// Circular buffer for momentary window (400 ms)
	private momentaryLen: number;
	private momentaryBuf: Float64Array;
	private momentaryPos = 0;
	private momentarySum = 0;

	// Circular buffer for short-term window (3 s)
	private shortTermLen: number;
	private shortTermBuf: Float64Array;
	private shortTermPos = 0;
	private shortTermSum = 0;

	constructor(sampleRate = 16000) {
		this.sampleRate = sampleRate;
		this.preFilter = makePreFilter();
		this.rlbFilter = makeRlbFilter();

		this.momentaryLen = Math.round(sampleRate * 0.4);
		this.momentaryBuf = new Float64Array(this.momentaryLen);
		this.shortTermLen = Math.round(sampleRate * 3.0);
		this.shortTermBuf = new Float64Array(this.shortTermLen);
	}

	/** Feed a block of Float32 PCM samples (normalised -1..+1). */
	process(samples: Float32Array): void {
		for (let i = 0; i < samples.length; i++) {
			// Apply K-weighting
			const s1 = this.preFilter.process(samples[i]);
			const s2 = this.rlbFilter.process(s1);
			const sq = s2 * s2;

			// Update momentary ring buffer
			this.momentarySum -= this.momentaryBuf[this.momentaryPos];
			this.momentaryBuf[this.momentaryPos] = sq;
			this.momentarySum += sq;
			this.momentaryPos = (this.momentaryPos + 1) % this.momentaryLen;

			// Update short-term ring buffer
			this.shortTermSum -= this.shortTermBuf[this.shortTermPos];
			this.shortTermBuf[this.shortTermPos] = sq;
			this.shortTermSum += sq;
			this.shortTermPos = (this.shortTermPos + 1) % this.shortTermLen;
		}
	}

	/**
	 * Returns momentary LUFS (400 ms window).
	 * Returns NEG_INF_LUFS (-144) when silent.
	 */
	getMomentary(): number {
		const mean = this.momentarySum / this.momentaryLen;
		if (mean <= 0) return NEG_INF_LUFS;
		return -0.691 + 10 * Math.log10(mean);
	}

	/**
	 * Returns short-term LUFS (3 s window).
	 * Returns NEG_INF_LUFS (-144) when silent.
	 */
	getShortTerm(): number {
		const mean = this.shortTermSum / this.shortTermLen;
		if (mean <= 0) return NEG_INF_LUFS;
		return -0.691 + 10 * Math.log10(mean);
	}

	reset(): void {
		this.preFilter.reset();
		this.rlbFilter.reset();
		this.momentaryBuf.fill(0);
		this.momentarySum = 0;
		this.momentaryPos = 0;
		this.shortTermBuf.fill(0);
		this.shortTermSum = 0;
		this.shortTermPos = 0;
	}

	get sampleRateHz(): number {
		return this.sampleRate;
	}
}
