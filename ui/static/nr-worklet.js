/**
 * NR (Noise Reduction) AudioWorkletProcessor.
 *
 * Algorithm: Wiener filter approximation using exponential moving average
 * of the noise floor estimate.  Simple, low-latency, and suitable for
 * an AudioWorklet context where FFT libraries are unavailable.
 *
 * Each 128-sample block:
 *  1. Compute per-sample squared magnitude.
 *  2. Update a smoothed "noise floor" estimate with a slow EMA (alpha_noise).
 *  3. Compute a Wiener gain G = max(0, 1 - k * noise_floor / signal_power).
 *  4. Apply G to the output block.
 *
 * Parameters:
 *  - amount: 0.0 (off) → 1.0 (aggressive), default 0.5.
 *  - enabled: 1 (true) / 0 (false), default 0.
 */
class NrProcessor extends AudioWorkletProcessor {
	static get parameterDescriptors() {
		return [
			{
				name: 'amount',
				defaultValue: 0.5,
				minValue: 0.0,
				maxValue: 1.0,
				automationRate: 'k-rate',
			},
			{
				name: 'enabled',
				defaultValue: 0,
				minValue: 0,
				maxValue: 1,
				automationRate: 'k-rate',
			},
		];
	}

	constructor() {
		super();
		// Smoothed noise floor estimate (per-sample energy, not per-block)
		this._noisePower = 1e-10;
	}

	process(inputs, outputs, parameters) {
		const input = inputs[0]?.[0];
		const output = outputs[0]?.[0];
		if (!input || !output) return true;

		const amount = parameters['amount'][0] ?? 0.5;
		const enabled = (parameters['enabled'][0] ?? 0) > 0.5;

		if (!enabled || amount < 0.001) {
			// Bypass — copy input to output unchanged
			output.set(input);
			return true;
		}

		const n = input.length;

		// Compute block RMS power
		let sumSq = 0;
		for (let i = 0; i < n; i++) {
			sumSq += input[i] * input[i];
		}
		const blockPower = sumSq / n;

		// Update noise floor with slow EMA when block is quiet
		// alpha_noise: smaller = slower adaptation
		const alphaNoise = 0.01;
		const alphaSig = 0.3;

		if (blockPower < this._noisePower * 2) {
			// Quiet period: update noise estimate
			this._noisePower =
				alphaNoise * blockPower + (1 - alphaNoise) * this._noisePower;
		} else {
			// Active signal: very slowly decay estimate
			this._noisePower = alphaSig * this._noisePower + (1 - alphaSig) * this._noisePower;
		}

		// Wiener gain — scales how aggressively noise is removed
		// k scales with amount parameter (0 = no NR, 1 = max NR factor of 4)
		const k = 1 + amount * 3; // k in [1, 4]
		const gain =
			blockPower > 1e-12
				? Math.max(0, 1 - (k * this._noisePower) / blockPower)
				: 0;

		for (let i = 0; i < n; i++) {
			output[i] = input[i] * gain;
		}

		return true;
	}
}

registerProcessor('nr-processor', NrProcessor);
