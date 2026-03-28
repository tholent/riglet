<script lang="ts">
	import type { ControlWebSocket } from '$lib/websocket.js';

	interface Props {
		tone: number;
		controlWs: ControlWebSocket | null;
	}
	let { tone, controlWs }: Props = $props();

	const TONES: number[] = [
		0, 67.0, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5, 94.8, 97.4,
		100.0, 103.5, 107.2, 110.9, 114.8, 118.8, 123.0, 127.3, 131.8, 136.5,
		141.3, 146.2, 151.4, 156.7, 162.2, 167.9, 173.8, 179.9, 186.2, 192.8,
		203.5, 210.7, 218.1, 225.7, 233.6, 241.8, 250.3,
	];

	function onChange(e: Event) {
		const target = e.currentTarget as HTMLSelectElement;
		const value = parseFloat(target.value);
		controlWs?.send({ type: 'ctcss', tone: value });
	}
</script>

<div class="ctcss-selector">
	<label class="ctcss-label" for="ctcss-select">CTCSS</label>
	<select
		id="ctcss-select"
		class="ctcss-select"
		value={tone}
		onchange={onChange}
		aria-label="CTCSS tone selector"
	>
		{#each TONES as t}
			<option value={t}>{t === 0 ? 'Off' : `${t.toFixed(1)} Hz`}</option>
		{/each}
	</select>
</div>

<style>
	.ctcss-selector {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.ctcss-label {
		font-size: 0.75rem;
		font-weight: 700;
		color: #888;
		letter-spacing: 0.05em;
		white-space: nowrap;
	}

	.ctcss-select {
		flex: 1;
		background: #1a1a1a;
		color: #ccc;
		border: 1px solid #444;
		border-radius: 4px;
		padding: 4px 8px;
		font-size: 0.85rem;
		cursor: pointer;
		appearance: auto;
	}

	.ctcss-select:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
	}

	.ctcss-select:hover {
		border-color: #666;
	}
</style>
