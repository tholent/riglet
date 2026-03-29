<script lang="ts">
	import type { ControlWebSocket } from '$lib/websocket.js';
	import { getBands } from '$lib/bandplan.js';
	import type { BandDef } from '$lib/bandplan.js';

	interface Props {
		controlWs: ControlWebSocket | null;
		currentFreq: number;
		/** Region code, e.g. 'us', 'eu', 'au'. Defaults to 'us'. */
		region?: string;
		/** Band names that are enabled for this radio. Pills not in this list are greyed out. */
		enabledBands?: string[];
	}
	let { controlWs, currentFreq, region = 'us', enabledBands = [] }: Props = $props();

	// Derive band list from region; fall back to US on error
	const bands = $derived((): BandDef[] => {
		try {
			return getBands(region);
		} catch {
			return getBands('us');
		}
	});

	function isActive(band: BandDef): boolean {
		return currentFreq >= band.lower_mhz && currentFreq <= band.upper_mhz;
	}

	function isEnabled(band: BandDef): boolean {
		// If enabledBands is empty (not configured), treat all as interactive
		if (enabledBands.length === 0) return true;
		return enabledBands.includes(band.name);
	}

	function jumpToBand(band: BandDef) {
		if (!isEnabled(band)) return;
		// Use midpoint as the default frequency when jumping
		const defaultMhz = (band.lower_mhz + band.upper_mhz) / 2;
		controlWs?.send({ type: 'freq', freq: defaultMhz });
	}

	function onBandKeydown(e: KeyboardEvent, band: BandDef, index: number) {
		if (!isEnabled(band)) return;
		const allBands = bands();
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			jumpToBand(band);
		} else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
			e.preventDefault();
			const next = allBands[index + 1];
			if (next) {
				const el = document.querySelector<HTMLButtonElement>(`[data-band="${next.name}"]`);
				el?.focus();
			}
		} else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
			e.preventDefault();
			const prev = allBands[index - 1];
			if (prev) {
				const el = document.querySelector<HTMLButtonElement>(`[data-band="${prev.name}"]`);
				el?.focus();
			}
		}
	}
</script>

<div class="band-selector" role="group" aria-label="Band selector">
	{#each bands() as band, i}
		{@const enabled = isEnabled(band)}
		<button
			class="band-pill"
			class:active={isActive(band)}
			class:disabled={!enabled}
			onclick={() => jumpToBand(band)}
			onkeydown={(e) => onBandKeydown(e, band, i)}
			aria-label={`${band.name} band (${band.lower_mhz}–${band.upper_mhz} MHz)${!enabled ? ' — not enabled for this radio' : ''}`}
			aria-pressed={isActive(band)}
			aria-disabled={!enabled}
			data-band={band.name}
			title={!enabled ? 'Not enabled for this radio' : undefined}
		>
			{band.name}
		</button>
	{/each}
</div>

<style>
	.band-selector {
		display: flex;
		flex-direction: row;
		flex-wrap: wrap;
		gap: 4px;
		align-items: center;
		justify-content: center;
	}

	.band-pill {
		padding: 4px 10px;
		border: 1px solid #444;
		border-radius: 12px;
		background: #1a1a1a;
		color: #aaa;
		font-size: 0.8rem;
		cursor: pointer;
		transition: all 0.12s;
		white-space: nowrap;
	}

	.band-pill:hover:not(.active):not(.disabled) {
		border-color: #666;
		color: #ccc;
	}

	.band-pill.active {
		border-color: #4a9eff;
		color: #4a9eff;
	}

	.band-pill.disabled {
		opacity: 0.35;
		pointer-events: none;
		cursor: default;
	}

	.band-pill:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
	}

	@media (prefers-reduced-motion: reduce) {
		.band-pill {
			transition: none;
		}
	}
</style>
