<script lang="ts">
	import type { ControlWebSocket } from '$lib/websocket.js';

	interface Props {
		vfo: string;
		controlWs: ControlWebSocket | null;
	}
	let { vfo, controlWs }: Props = $props();

	function toggle() {
		const next = vfo === 'VFOA' ? 'VFOB' : 'VFOA';
		controlWs?.send({ type: 'vfo', vfo: next });
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			toggle();
		}
	}
</script>

<div class="vfo-selector">
	<button
		class="vfo-btn"
		class:vfoa={vfo === 'VFOA'}
		class:vfob={vfo === 'VFOB'}
		onclick={toggle}
		onkeydown={onKeydown}
		aria-label={`VFO ${vfo === 'VFOA' ? 'A active, switch to B' : 'B active, switch to A'}`}
		aria-pressed={undefined}
	>
		<span class="vfo-label">VFO</span>
		<span class="vfo-value">{vfo === 'VFOA' ? 'A' : 'B'}</span>
	</button>
</div>

<style>
	.vfo-selector {
		display: flex;
		align-items: center;
	}

	.vfo-btn {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 6px 14px;
		border: 1px solid #444;
		border-radius: 6px;
		background: #1a1a1a;
		color: #aaa;
		font-size: 0.9rem;
		font-weight: 700;
		cursor: pointer;
		transition: all 0.12s;
		letter-spacing: 0.05em;
	}

	.vfo-btn:hover {
		border-color: #666;
		color: #ccc;
	}

	.vfo-btn.vfoa {
		border-color: #4a9eff;
		color: #4a9eff;
	}

	.vfo-btn.vfob {
		border-color: #ff9f4a;
		color: #ff9f4a;
	}

	.vfo-label {
		font-size: 0.75rem;
		color: #666;
		font-weight: 400;
	}

	.vfo-btn:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
	}

	@media (prefers-reduced-motion: reduce) {
		.vfo-btn {
			transition: none;
		}
	}
</style>
