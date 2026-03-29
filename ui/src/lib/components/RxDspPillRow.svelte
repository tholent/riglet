<script lang="ts">
	import type { RxDspChain } from '$lib/audio/rx-dsp-chain.js';
	import { createEventDispatcher } from 'svelte';

	interface Props {
		rxDspChain: RxDspChain | null;
	}
	let { rxDspChain }: Props = $props();

	const dispatch = createEventDispatcher<{ change: { filter: string; enabled: boolean } }>();

	// Local enabled state for each filter (drives pill appearance)
	let hpEnabled = $state(false);
	let lpEnabled = $state(false);
	let peakEnabled = $state(false);
	let nbEnabled = $state(false);
	let notchEnabled = $state(false);
	let bpEnabled = $state(false);
	let nrEnabled = $state(false);

	// Popover anchor placeholder — Task 18 will wire per-filter popovers here
	// let openPopover: string | null = $state(null);

	function toggle(
		filter: string,
		enabled: boolean,
		applyFn: (chain: RxDspChain, val: boolean) => void,
	): void {
		if (!rxDspChain) return;
		applyFn(rxDspChain, enabled);
		dispatch('change', { filter, enabled });
	}

	function toggleHp(): void {
		if (!rxDspChain) return;
		hpEnabled = !hpEnabled;
		toggle('highpass', hpEnabled, (c, v) => c.enableHighpass(v));
	}

	function toggleLp(): void {
		if (!rxDspChain) return;
		lpEnabled = !lpEnabled;
		toggle('lowpass', lpEnabled, (c, v) => c.enableLowpass(v));
	}

	function togglePeak(): void {
		if (!rxDspChain) return;
		peakEnabled = !peakEnabled;
		toggle('peak', peakEnabled, (c, v) => c.enablePeak(v));
	}

	function toggleNb(): void {
		if (!rxDspChain) return;
		nbEnabled = !nbEnabled;
		toggle('noiseBlanker', nbEnabled, (c, v) => c.enableNoiseBlanker(v));
	}

	function toggleNotch(): void {
		if (!rxDspChain) return;
		notchEnabled = !notchEnabled;
		toggle('notch', notchEnabled, (c, v) => c.enableNotch(v));
	}

	function toggleBp(): void {
		if (!rxDspChain) return;
		bpEnabled = !bpEnabled;
		toggle('bandpass', bpEnabled, (c, v) => c.enableBandpass(v));
	}

	function toggleNr(): void {
		if (!rxDspChain) return;
		nrEnabled = !nrEnabled;
		toggle('nr', nrEnabled, (c, v) => c.enableNr(v));
	}
</script>

<div class="pill-row" role="group" aria-label="RX DSP filter controls">
	<button
		class="pill"
		class:active={hpEnabled}
		class:unavailable={!rxDspChain}
		disabled={!rxDspChain}
		aria-pressed={hpEnabled}
		aria-label="Highpass filter"
		onclick={toggleHp}
	>HP</button>

	<button
		class="pill"
		class:active={lpEnabled}
		class:unavailable={!rxDspChain}
		disabled={!rxDspChain}
		aria-pressed={lpEnabled}
		aria-label="Lowpass filter"
		onclick={toggleLp}
	>LP</button>

	<button
		class="pill"
		class:active={peakEnabled}
		class:unavailable={!rxDspChain}
		disabled={!rxDspChain}
		aria-pressed={peakEnabled}
		aria-label="Peak filter"
		onclick={togglePeak}
	>Peak</button>

	<button
		class="pill"
		class:active={nbEnabled}
		class:unavailable={!rxDspChain}
		disabled={!rxDspChain}
		aria-pressed={nbEnabled}
		aria-label="Noise blanker"
		onclick={toggleNb}
	>NB</button>

	<button
		class="pill"
		class:active={notchEnabled}
		class:unavailable={!rxDspChain}
		disabled={!rxDspChain}
		aria-pressed={notchEnabled}
		aria-label="Notch filter"
		onclick={toggleNotch}
	>Notch</button>

	<button
		class="pill"
		class:active={bpEnabled}
		class:unavailable={!rxDspChain}
		disabled={!rxDspChain}
		aria-pressed={bpEnabled}
		aria-label="Bandpass filter"
		onclick={toggleBp}
	>BP</button>

	<button
		class="pill"
		class:active={nrEnabled}
		class:unavailable={!rxDspChain}
		disabled={!rxDspChain}
		aria-pressed={nrEnabled}
		aria-label="Noise reduction"
		onclick={toggleNr}
	>NR</button>
</div>

<style>
	.pill-row {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
		align-items: center;
	}

	.pill {
		padding: 2px 9px;
		border-radius: 99px;
		border: 1px solid #444;
		background: #1a1a1a;
		color: #666;
		font-size: 0.72rem;
		font-weight: 600;
		letter-spacing: 0.04em;
		cursor: pointer;
		transition: background 0.1s, border-color 0.1s, color 0.1s;
		white-space: nowrap;
	}

	.pill:hover:not(.active):not(:disabled) {
		border-color: #666;
		color: #aaa;
	}

	.pill.active {
		background: #0284c7;
		border-color: #0ea5e9;
		color: #fff;
	}

	.pill:disabled,
	.pill.unavailable {
		opacity: 0.35;
		cursor: not-allowed;
	}

	.pill:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
	}

	@media (prefers-reduced-motion: reduce) {
		.pill {
			transition: none;
		}
	}
</style>
