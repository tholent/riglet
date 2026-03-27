<script lang="ts">
	import type { ControlWebSocket } from '$lib/websocket.js';

	interface Props {
		freq: number;
		controlWs: ControlWebSocket | null;
	}
	let { freq, controlWs }: Props = $props();

	let editing = $state(false);
	let editValue = $state('');

	// Common amateur bands (MHz): label -> center freq
	const BANDS: { label: string; freq: number }[] = [
		{ label: '160m', freq: 1.9 },
		{ label: '80m', freq: 3.75 },
		{ label: '40m', freq: 7.1 },
		{ label: '20m', freq: 14.2 },
		{ label: '17m', freq: 18.1 },
		{ label: '15m', freq: 21.2 },
		{ label: '10m', freq: 28.5 },
	];

	function startEdit() {
		editValue = freq.toFixed(6);
		editing = true;
	}

	function commitEdit() {
		const parsed = parseFloat(editValue);
		if (!isNaN(parsed) && parsed > 0) {
			controlWs?.send({ type: 'freq', freq: parsed });
		}
		editing = false;
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') commitEdit();
		if (e.key === 'Escape') editing = false;
	}

	function jumpTo(mhz: number) {
		controlWs?.send({ type: 'freq', freq: mhz });
	}

	function nudge(direction: 1 | -1) {
		controlWs?.send({ type: 'nudge', direction });
	}
</script>

<div class="freq-block">
	<div class="freq-row">
		<button class="nudge" onclick={() => nudge(-1)} aria-label="Tune down 1 kHz">−</button>

		{#if editing}
			<!-- svelte-ignore a11y_autofocus -->
			<input
				autofocus
				class="freq-input"
				type="text"
				bind:value={editValue}
				onblur={commitEdit}
				onkeydown={onKeydown}
			/>
		{:else}
			<button class="freq-display" onclick={startEdit} aria-label="Click to edit frequency">
				{freq.toFixed(3)} <span class="unit">MHz</span>
			</button>
		{/if}

		<button class="nudge" onclick={() => nudge(1)} aria-label="Tune up 1 kHz">+</button>
	</div>

	<div class="bands">
		{#each BANDS as band}
			<button class="band-pill" onclick={() => jumpTo(band.freq)}>{band.label}</button>
		{/each}
	</div>
</div>

<style>
	.freq-block {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.freq-row {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.freq-display {
		font-size: 2.2rem;
		font-family: 'Courier New', monospace;
		font-weight: 700;
		color: #4cff8a;
		background: #0a0a0a;
		border: 1px solid #333;
		border-radius: 4px;
		padding: 8px 16px;
		cursor: pointer;
		letter-spacing: 0.05em;
		min-width: 240px;
		text-align: center;
	}

	.freq-display:hover {
		border-color: #4a9eff;
	}

	.unit {
		font-size: 1rem;
		color: #888;
		font-weight: 400;
	}

	.freq-input {
		font-size: 2.2rem;
		font-family: 'Courier New', monospace;
		font-weight: 700;
		color: #4cff8a;
		background: #0a0a0a;
		border: 1px solid #4a9eff;
		border-radius: 4px;
		padding: 8px 16px;
		min-width: 240px;
		text-align: center;
	}

	.nudge {
		font-size: 1.6rem;
		width: 44px;
		height: 44px;
		background: #1a1a1a;
		border: 1px solid #444;
		border-radius: 4px;
		color: #ccc;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0;
	}

	.nudge:hover { background: #2a2a2a; border-color: #666; }

	.bands {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
	}

	.band-pill {
		padding: 4px 10px;
		border: 1px solid #444;
		border-radius: 12px;
		background: #1a1a1a;
		color: #aaa;
		font-size: 0.8rem;
		cursor: pointer;
	}

	.band-pill:hover { border-color: #4a9eff; color: #4a9eff; }
</style>
