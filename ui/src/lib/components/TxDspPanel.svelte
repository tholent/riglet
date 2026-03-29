<script lang="ts">
	import type { TxDspChain, CompressorPreset } from '$lib/audio/tx-dsp-chain.js';
	import { createEventDispatcher } from 'svelte';
	import TxDspMenu from './TxDspMenu.svelte';

	interface Props {
		txDspChain: TxDspChain | null;
	}
	let { txDspChain }: Props = $props();

	const dispatch = createEventDispatcher<{ change: { param: string; value: unknown } }>();

	let open = $state(false);

	// Track active stage count for the badge by listening to change events
	let hpEnabled = $state(false);
	let lpEnabled = $state(false);
	let eqEnabled = $state(false);
	let compEnabled = $state(false);
	let limEnabled = $state(false);
	let gateEnabled = $state(false);

	let activeCount = $derived(
		[hpEnabled, lpEnabled, eqEnabled, compEnabled, limEnabled, gateEnabled].filter(Boolean).length,
	);

	function toggleOpen(): void {
		open = !open;
	}

	function onMenuChange(e: CustomEvent<{ param: string; value: unknown }>): void {
		const { param, value } = e.detail;
		// Mirror enabled flags so the badge stays accurate
		if (param === 'hp_enabled')   hpEnabled   = value as boolean;
		if (param === 'lp_enabled')   lpEnabled   = value as boolean;
		if (param === 'eq_enabled')   eqEnabled   = value as boolean;
		if (param === 'comp_enabled') compEnabled = value as boolean;
		if (param === 'lim_enabled')  limEnabled  = value as boolean;
		if (param === 'gate_enabled') gateEnabled = value as boolean;
		dispatch('change', { param, value });
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="tx-dsp-wrap">
	<button
		class="tx-dsp-trigger"
		class:open
		onclick={toggleOpen}
		aria-expanded={open}
		aria-haspopup="dialog"
		aria-label="TX DSP settings"
	>
		<span class="label">TX DSP</span>
		{#if activeCount > 0}
			<span class="badge" aria-label="{activeCount} active">{activeCount}</span>
		{/if}
	</button>

	<TxDspMenu bind:open {txDspChain} onchange={onMenuChange} />
</div>

<style>
	.tx-dsp-wrap {
		position: relative;
		display: inline-block;
	}

	.tx-dsp-trigger {
		display: flex;
		align-items: center;
		gap: 5px;
		padding: 4px 12px;
		background: #1a1a1a;
		border: 1px solid #444;
		border-radius: 4px;
		color: #aaa;
		font-size: 0.78rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		cursor: pointer;
		transition: background 0.1s, border-color 0.1s, color 0.1s;
	}

	.tx-dsp-trigger:hover {
		border-color: #666;
		color: #ccc;
	}

	.tx-dsp-trigger.open {
		background: #1b2f3b;
		border-color: #0ea5e9;
		color: #38bdf8;
	}

	.tx-dsp-trigger:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
	}

	.badge {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 16px;
		height: 16px;
		border-radius: 50%;
		background: #0284c7;
		color: #fff;
		font-size: 0.65rem;
		font-weight: 700;
		line-height: 1;
	}

	@media (prefers-reduced-motion: reduce) {
		.tx-dsp-trigger {
			transition: none;
		}
	}
</style>
