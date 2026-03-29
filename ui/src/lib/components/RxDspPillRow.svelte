<script lang="ts">
	import type { RxDspChain } from '$lib/audio/rx-dsp-chain.js';
	import { createEventDispatcher } from 'svelte';
	import RxDspPopover from './RxDspPopover.svelte';

	interface Props {
		rxDspChain: RxDspChain | null;
	}
	let { rxDspChain }: Props = $props();

	const dispatch = createEventDispatcher<{ change: Record<string, unknown> }>();

	// Which popover is currently open
	let openFilter = $state<string | null>(null);

	// Pill button element refs for popover anchoring
	let hpEl: HTMLButtonElement | undefined;
	let lpEl: HTMLButtonElement | undefined;
	let peakEl: HTMLButtonElement | undefined;
	let nbEl: HTMLButtonElement | undefined;
	let notchEl: HTMLButtonElement | undefined;
	let bpEl: HTMLButtonElement | undefined;
	let nrEl: HTMLButtonElement | undefined;

	// Active state for each filter — reflects enabled state from the popover
	let hpEnabled = $state(false);
	let lpEnabled = $state(false);
	let peakEnabled = $state(false);
	let nbEnabled = $state(false);
	let notchEnabled = $state(false);
	let bpEnabled = $state(false);
	let nrEnabled = $state(false);

	type FilterKey =
		| 'highpass'
		| 'lowpass'
		| 'peak'
		| 'noiseBlanker'
		| 'notch'
		| 'bandpass'
		| 'nr';

	function togglePopover(filter: FilterKey): void {
		if (!rxDspChain) return;
		openFilter = openFilter === filter ? null : filter;
	}

	function onPopoverChange(filter: FilterKey, detail: Record<string, unknown>): void {
		// Sync enabled state back to the pill
		const en = detail.enabled as boolean;
		switch (filter) {
			case 'highpass':    hpEnabled = en; break;
			case 'lowpass':     lpEnabled = en; break;
			case 'peak':        peakEnabled = en; break;
			case 'noiseBlanker': nbEnabled = en; break;
			case 'notch':       notchEnabled = en; break;
			case 'bandpass':    bpEnabled = en; break;
			case 'nr':          nrEnabled = en; break;
		}
		dispatch('change', { filter, ...detail });
	}

	// Keep openFilter falsy when chain goes away
	$effect(() => {
		if (!rxDspChain) openFilter = null;
	});
</script>

<div class="pill-row" role="group" aria-label="RX DSP filter controls">

	<button
		class="pill"
		class:active={hpEnabled}
		class:unavailable={!rxDspChain}
		disabled={!rxDspChain}
		aria-pressed={hpEnabled}
		aria-label="Highpass filter"
		aria-haspopup="dialog"
		bind:this={hpEl}
		onclick={() => togglePopover('highpass')}
	>HP</button>

	<button
		class="pill"
		class:active={lpEnabled}
		class:unavailable={!rxDspChain}
		disabled={!rxDspChain}
		aria-pressed={lpEnabled}
		aria-label="Lowpass filter"
		aria-haspopup="dialog"
		bind:this={lpEl}
		onclick={() => togglePopover('lowpass')}
	>LP</button>

	<button
		class="pill"
		class:active={peakEnabled}
		class:unavailable={!rxDspChain}
		disabled={!rxDspChain}
		aria-pressed={peakEnabled}
		aria-label="Peak filter"
		aria-haspopup="dialog"
		bind:this={peakEl}
		onclick={() => togglePopover('peak')}
	>Peak</button>

	<button
		class="pill"
		class:active={nbEnabled}
		class:unavailable={!rxDspChain}
		disabled={!rxDspChain}
		aria-pressed={nbEnabled}
		aria-label="Noise blanker"
		aria-haspopup="dialog"
		bind:this={nbEl}
		onclick={() => togglePopover('noiseBlanker')}
	>NB</button>

	<button
		class="pill"
		class:active={notchEnabled}
		class:unavailable={!rxDspChain}
		disabled={!rxDspChain}
		aria-pressed={notchEnabled}
		aria-label="Notch filter"
		aria-haspopup="dialog"
		bind:this={notchEl}
		onclick={() => togglePopover('notch')}
	>Notch</button>

	<button
		class="pill"
		class:active={bpEnabled}
		class:unavailable={!rxDspChain}
		disabled={!rxDspChain}
		aria-pressed={bpEnabled}
		aria-label="Bandpass filter"
		aria-haspopup="dialog"
		bind:this={bpEl}
		onclick={() => togglePopover('bandpass')}
	>BP</button>

	<button
		class="pill"
		class:active={nrEnabled}
		class:unavailable={!rxDspChain}
		disabled={!rxDspChain}
		aria-pressed={nrEnabled}
		aria-label="Noise reduction"
		aria-haspopup="dialog"
		bind:this={nrEl}
		onclick={() => togglePopover('nr')}
	>NR</button>

</div>

<!-- Popovers — one per filter, shown when openFilter matches -->

<RxDspPopover
	{rxDspChain}
	filter="highpass"
	bind:open={() => openFilter === 'highpass', (v) => { if (!v) openFilter = null; }}
	anchor={hpEl ?? null}
	onchange={(e) => onPopoverChange('highpass', e.detail)}
/>

<RxDspPopover
	{rxDspChain}
	filter="lowpass"
	bind:open={() => openFilter === 'lowpass', (v) => { if (!v) openFilter = null; }}
	anchor={lpEl ?? null}
	onchange={(e) => onPopoverChange('lowpass', e.detail)}
/>

<RxDspPopover
	{rxDspChain}
	filter="peak"
	bind:open={() => openFilter === 'peak', (v) => { if (!v) openFilter = null; }}
	anchor={peakEl ?? null}
	onchange={(e) => onPopoverChange('peak', e.detail)}
/>

<RxDspPopover
	{rxDspChain}
	filter="noiseBlanker"
	bind:open={() => openFilter === 'noiseBlanker', (v) => { if (!v) openFilter = null; }}
	anchor={nbEl ?? null}
	onchange={(e) => onPopoverChange('noiseBlanker', e.detail)}
/>

<RxDspPopover
	{rxDspChain}
	filter="notch"
	bind:open={() => openFilter === 'notch', (v) => { if (!v) openFilter = null; }}
	anchor={notchEl ?? null}
	onchange={(e) => onPopoverChange('notch', e.detail)}
/>

<RxDspPopover
	{rxDspChain}
	filter="bandpass"
	bind:open={() => openFilter === 'bandpass', (v) => { if (!v) openFilter = null; }}
	anchor={bpEl ?? null}
	onchange={(e) => onPopoverChange('bandpass', e.detail)}
/>

<RxDspPopover
	{rxDspChain}
	filter="nr"
	bind:open={() => openFilter === 'nr', (v) => { if (!v) openFilter = null; }}
	anchor={nrEl ?? null}
	onchange={(e) => onPopoverChange('nr', e.detail)}
/>

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
