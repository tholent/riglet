<script lang="ts">
	import type { ControlWebSocket } from '$lib/websocket.js';

	interface Props {
		ptt: boolean;
		controlWs: ControlWebSocket | null;
	}
	let { ptt, controlWs }: Props = $props();

	function toggle() {
		controlWs?.send({ type: 'ptt', active: !ptt });
	}

	// Support press-and-hold: send PTT on pointerdown, release on pointerup
	function onPointerDown(e: PointerEvent) {
		(e.target as HTMLElement).setPointerCapture(e.pointerId);
		if (!ptt) controlWs?.send({ type: 'ptt', active: true });
	}

	function onPointerUp() {
		if (ptt) controlWs?.send({ type: 'ptt', active: false });
	}
</script>

<div class="ptt-wrap">
	<button
		class="ptt-btn"
		class:active={ptt}
		onpointerdown={onPointerDown}
		onpointerup={onPointerUp}
		aria-label={ptt ? 'Transmitting — click to release PTT' : 'Push to Talk'}
		aria-pressed={ptt}
	>
		{ptt ? 'TX' : 'PTT'}
	</button>
	{#if ptt}
		<span class="tx-indicator">TRANSMITTING</span>
	{/if}
</div>

<style>
	.ptt-wrap {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8px;
	}

	.ptt-btn {
		width: 96px;
		height: 96px;
		border-radius: 50%;
		border: 3px solid #555;
		background: #1a1a1a;
		color: #ccc;
		font-size: 1.4rem;
		font-weight: 700;
		cursor: pointer;
		transition: background 0.1s, border-color 0.1s, color 0.1s;
		touch-action: none;
		user-select: none;
	}

	.ptt-btn:hover:not(.active) {
		border-color: #888;
		color: #fff;
	}

	.ptt-btn.active {
		background: #c62828;
		border-color: #ef5350;
		color: #fff;
		box-shadow: 0 0 16px rgba(239, 83, 80, 0.6);
	}

	.tx-indicator {
		font-size: 0.75rem;
		font-weight: 700;
		color: #ef5350;
		letter-spacing: 0.1em;
		animation: blink 0.8s step-end infinite;
	}

	@keyframes blink {
		0%, 100% { opacity: 1; }
		50% { opacity: 0; }
	}
</style>
