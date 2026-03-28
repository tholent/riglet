<script lang="ts">
	import type { ControlWebSocket } from '$lib/websocket.js';

	interface Props {
		freq: number;
		controlWs: ControlWebSocket | null;
	}
	let { freq, controlWs }: Props = $props();

	let editing = $state(false);
	let editValue = $state('');

	// Format freq (MHz float) as XX.XXX.XXX with dot separators.
	// E.g. 14.2 -> "14.200.000", 7.03815 -> "7.038.150", 146.52 -> "146.520.000"
	function formatFreq(mhz: number): string {
		const hz = Math.round(mhz * 1_000_000);
		// Split into three groups from the right: ones+tens+hundreds (kHz sub), kHz, MHz
		const sub   = hz % 1000;           // 0–999
		const khz   = Math.floor(hz / 1000) % 1000; // 0–999
		const mhzPart = Math.floor(hz / 1_000_000);  // leading group, no zero-pad
		return `${mhzPart}.${String(khz).padStart(3, '0')}.${String(sub).padStart(3, '0')}`;
	}

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

	function nudge(direction: 1 | -1) {
		controlWs?.send({ type: 'nudge', direction });
	}
</script>

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
			{formatFreq(freq)}<span class="unit"> MHz</span>
		</button>
	{/if}

	<button class="nudge" onclick={() => nudge(1)} aria-label="Tune up 1 kHz">+</button>
</div>

<style>
	.freq-row {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}

	.freq-display {
		font-size: 3.5rem;
		font-family: 'Courier New', monospace;
		font-weight: 700;
		color: #4cff8a;
		background: #0a0a0a;
		border: 1px solid #333;
		border-radius: 4px;
		padding: 4px 12px;
		cursor: pointer;
		letter-spacing: 0.02em;
		white-space: nowrap;
		line-height: 1;
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
		font-size: 3.5rem;
		font-family: 'Courier New', monospace;
		font-weight: 700;
		color: #4cff8a;
		background: #0a0a0a;
		border: 1px solid #4a9eff;
		border-radius: 4px;
		padding: 4px 12px;
		white-space: nowrap;
		line-height: 1;
		min-width: 260px;
	}

	.nudge {
		font-size: 1.4rem;
		width: 36px;
		height: 36px;
		background: #1a1a1a;
		border: 1px solid #444;
		border-radius: 4px;
		color: #ccc;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0;
		flex-shrink: 0;
	}

	.nudge:hover { background: #2a2a2a; border-color: #666; }
</style>
