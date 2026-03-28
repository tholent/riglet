<script lang="ts">
	import type { ControlWebSocket } from '$lib/websocket.js';

	interface Band {
		label: string;
		defaultMhz: number;
		rangeLow: number;
		rangeHigh: number;
	}

	interface Props {
		controlWs: ControlWebSocket | null;
		currentFreq: number;
	}
	let { controlWs, currentFreq }: Props = $props();

	const BANDS: Band[] = [
		{ label: '160m', defaultMhz: 1.900,  rangeLow: 1.800,  rangeHigh: 2.000  },
		{ label: '80m',  defaultMhz: 3.750,  rangeLow: 3.500,  rangeHigh: 4.000  },
		{ label: '40m',  defaultMhz: 7.100,  rangeLow: 7.000,  rangeHigh: 7.300  },
		{ label: '30m',  defaultMhz: 10.120, rangeLow: 10.100, rangeHigh: 10.150 },
		{ label: '20m',  defaultMhz: 14.200, rangeLow: 14.000, rangeHigh: 14.350 },
		{ label: '17m',  defaultMhz: 18.100, rangeLow: 18.068, rangeHigh: 18.168 },
		{ label: '15m',  defaultMhz: 21.200, rangeLow: 21.000, rangeHigh: 21.450 },
		{ label: '12m',  defaultMhz: 24.940, rangeLow: 24.890, rangeHigh: 24.990 },
		{ label: '10m',  defaultMhz: 28.500, rangeLow: 28.000, rangeHigh: 29.700 },
		{ label: '6m',   defaultMhz: 50.150, rangeLow: 50.000, rangeHigh: 54.000 },
	];

	function isActive(band: Band): boolean {
		return currentFreq >= band.rangeLow && currentFreq <= band.rangeHigh;
	}

	function jumpToBand(band: Band) {
		controlWs?.send({ type: 'freq', freq: band.defaultMhz });
	}

	function onBandKeydown(e: KeyboardEvent, band: Band, index: number) {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			jumpToBand(band);
		} else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
			e.preventDefault();
			const next = BANDS[index + 1];
			if (next) {
				const el = document.querySelector<HTMLButtonElement>(`[data-band="${next.label}"]`);
				el?.focus();
			}
		} else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
			e.preventDefault();
			const prev = BANDS[index - 1];
			if (prev) {
				const el = document.querySelector<HTMLButtonElement>(`[data-band="${prev.label}"]`);
				el?.focus();
			}
		}
	}
</script>

<div class="band-selector" role="group" aria-label="Band selector">
	{#each BANDS as band, i}
		<button
			class="band-pill"
			class:active={isActive(band)}
			onclick={() => jumpToBand(band)}
			onkeydown={(e) => onBandKeydown(e, band, i)}
			aria-label={`${band.label} band (${band.rangeLow}–${band.rangeHigh} MHz)`}
			aria-pressed={isActive(band)}
			data-band={band.label}
		>
			{band.label}
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

	.band-pill:hover:not(.active) {
		border-color: #666;
		color: #ccc;
	}

	.band-pill.active {
		border-color: #4a9eff;
		color: #4a9eff;
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
