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
</script>

<div class="band-selector">
	{#each BANDS as band}
		<button
			class="band-pill"
			class:active={isActive(band)}
			onclick={() => jumpToBand(band)}
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
</style>
