<script lang="ts">
	import type { ControlWebSocket } from '$lib/websocket.js';

	interface Props {
		mode: string;
		controlWs: ControlWebSocket | null;
	}
	let { mode, controlWs }: Props = $props();

	const MODES = ['USB', 'LSB', 'AM', 'FM', 'CW', 'RTTY', 'FT8'];

	function select(m: string) {
		controlWs?.send({ type: 'mode', mode: m });
	}
</script>

<div class="mode-selector">
	{#each MODES as m}
		<button
			class="mode-btn"
			class:active={mode === m}
			onclick={() => select(m)}
		>
			{m}
		</button>
	{/each}
</div>

<style>
	.mode-selector {
		display: flex;
		gap: 4px;
		flex-wrap: wrap;
	}

	.mode-btn {
		padding: 4px 10px;
		border: 1px solid #444;
		border-radius: 4px;
		background: #1a1a1a;
		color: #aaa;
		font-size: 0.8rem;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.12s;
	}

	.mode-btn:hover:not(.active) {
		border-color: #666;
		color: #ccc;
	}

	.mode-btn.active {
		background: #4a9eff;
		border-color: #4a9eff;
		color: #fff;
	}
</style>
