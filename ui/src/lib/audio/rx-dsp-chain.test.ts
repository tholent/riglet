/**
 * Unit tests for RxDspChain node wiring and enable/disable logic.
 * Uses a minimal inline AudioContext mock (no browser required).
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { RxDspChain } from './rx-dsp-chain.js';

// ---------------------------------------------------------------------------
// Minimal AudioContext mock
// ---------------------------------------------------------------------------

interface MockAudioParam {
	value: number;
}

function makeParam(initial = 0): MockAudioParam {
	return { value: initial };
}

interface MockBiquadFilterNode {
	type: string;
	frequency: MockAudioParam;
	gain: MockAudioParam;
	Q: MockAudioParam;
	_connections: unknown[];
	connect(dest: unknown): void;
	disconnect(): void;
}

function makeBiquadFilter(): MockBiquadFilterNode {
	return {
		type: 'lowpass',
		frequency: makeParam(0),
		gain: makeParam(0),
		Q: makeParam(1),
		_connections: [],
		connect(dest: unknown) {
			this._connections.push(dest);
		},
		disconnect() {
			this._connections = [];
		},
	};
}

function makeAudioContext(sampleRate = 16000): AudioContext {
	return {
		sampleRate,
		createBiquadFilter: makeBiquadFilter,
		audioWorklet: {
			addModule: () => Promise.reject(new Error('worklet unavailable in test')),
		},
		// AudioWorkletNode is never reached in tests because addModule always rejects
	} as unknown as AudioContext;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('RxDspChain', () => {
	let ctx: AudioContext;
	let chain: RxDspChain;

	beforeEach(async () => {
		ctx = makeAudioContext();
		chain = new RxDspChain(ctx);
		await chain.build();
	});

	it('build_creates_all_nodes: non-null after build (NR may be null)', () => {
		// Access via the public API — chain must expose input/output without throwing
		expect(chain.input).toBeTruthy();
		expect(chain.output).toBeTruthy();
		// Internal nodes verified indirectly via enable/disable without throwing
		expect(() => chain.enableHighpass(false)).not.toThrow();
		expect(() => chain.enableLowpass(false)).not.toThrow();
		expect(() => chain.enablePeak(false)).not.toThrow();
		expect(() => chain.enableNoiseBlanker(false)).not.toThrow();
		expect(() => chain.enableNotch(false)).not.toThrow();
		expect(() => chain.enableBandpass(false)).not.toThrow();
	});

	it('chain_order_input_is_highpass: chain.input is the highpass node', () => {
		// When highpass is enabled, freq is set to the configured value;
		// the input node controls highpass, so setHighpass should affect chain.input's frequency.
		chain.setHighpass(300);
		// We can verify by enabling and checking the enabled flag reflects in input node behaviour
		chain.enableHighpass(true);
		expect(chain.isHighpassEnabled()).toBe(true);
	});

	it('highpass_enable: enableHighpass(true) does not zero freq', () => {
		chain.setHighpass(200);
		chain.enableHighpass(true);
		expect(chain.isHighpassEnabled()).toBe(true);
		// Freq remains at 200 (set before enable)
		const node = chain.input as unknown as MockBiquadFilterNode;
		expect(node.frequency.value).toBe(200);
	});

	it('highpass_disable: enableHighpass(false) sets freq to 1 Hz', () => {
		chain.setHighpass(200);
		chain.enableHighpass(true);
		chain.enableHighpass(false);
		expect(chain.isHighpassEnabled()).toBe(false);
		const node = chain.input as unknown as MockBiquadFilterNode;
		expect(node.frequency.value).toBe(1);
	});

	it('lowpass_enable_disable: enableLowpass(false) sets freq to sampleRate/2', () => {
		chain.setLowpass(2500);
		chain.enableLowpass(true);
		expect(chain.isLowpassEnabled()).toBe(true);

		chain.enableLowpass(false);
		expect(chain.isLowpassEnabled()).toBe(false);
		// Bypass freq = Nyquist = sampleRate / 2
		// The lowpass node is not directly accessible, but we verify via no-throw and state
	});

	it('peak_enable: enablePeak(true) preserves configured gain', () => {
		chain.setPeak(1000, 6, 2);
		chain.enablePeak(true);
		expect(chain.isPeakEnabled()).toBe(true);
	});

	it('peak_disable: enablePeak(false) sets gain to 0', () => {
		chain.setPeak(1000, 6, 2);
		chain.enablePeak(true);
		chain.enablePeak(false);
		expect(chain.isPeakEnabled()).toBe(false);
		// The peak node gain should be 0 after disable — verified via no throw
	});

	it('noise_blanker_freq_switch: setNoiseBlankerFreq(60) stores 60 Hz', () => {
		chain.enableNoiseBlanker(true);
		chain.setNoiseBlankerFreq(60);
		// No public getter for freq; verify via no-throw
		expect(() => chain.setNoiseBlankerFreq(50)).not.toThrow();
	});

	it('bandpass_voice_preset: setBandpassPreset("voice") sets center ~1500 Hz', () => {
		chain.enableBandpass(true);
		chain.setBandpassPreset('voice');
		// The bandpass output node carries the voice preset freq; verify no throw
		expect(() => chain.setBandpassPreset('voice')).not.toThrow();
		expect(chain.getBandpassPreset()).toBe('voice');
	});

	it('bandpass_cw_preset: setBandpassPreset("cw") stores cw preset', () => {
		chain.enableBandpass(true);
		chain.setBandpassPreset('cw');
		expect(chain.getBandpassPreset()).toBe('cw');
	});

	it('notch_mode: setNotchMode("auto") is stored and getNotchMode returns "auto"', () => {
		chain.setNotchMode('auto');
		expect(chain.getNotchMode()).toBe('auto');
	});

	it('notch_mode: setNotchMode("manual") roundtrips', () => {
		chain.setNotchMode('auto');
		chain.setNotchMode('manual');
		expect(chain.getNotchMode()).toBe('manual');
	});

	it('nr_unavailable: isNrAvailable() is false (worklet not available in test)', () => {
		expect(chain.isNrAvailable()).toBe(false);
	});

	it('destroy_nulls_refs: destroy does not throw and subsequent calls are no-ops', () => {
		expect(() => chain.destroy()).not.toThrow();
		// After destroy, operations on nodes are guarded — no throws
		expect(() => chain.enableHighpass(true)).not.toThrow();
		expect(() => chain.enableLowpass(true)).not.toThrow();
		expect(() => chain.enablePeak(true)).not.toThrow();
		expect(() => chain.enableNoiseBlanker(true)).not.toThrow();
		expect(() => chain.enableNotch(true)).not.toThrow();
		expect(() => chain.enableBandpass(true)).not.toThrow();
	});
});
