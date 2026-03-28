<script lang="ts">
	import type { ControlWebSocket } from '$lib/websocket.js';
	import { VoxDetector } from '$lib/audio/vox.js';

	interface Props {
		ptt: boolean;
		controlWs: ControlWebSocket | null;
		/** Optional PCM chunk fed from the microphone for VOX processing. */
		micSamples?: Float32Array | null;
	}
	let { ptt, controlWs, micSamples = null }: Props = $props();

	// VOX state
	let voxActive = $state(false);
	let voxDetecting = $state(false); // true when VOX is seeing voice activity

	const voxDetector = new VoxDetector({
		thresholdDb: -40,
		hangTimeMs: 500,
		antiVoxDelayMs: 50,
	});

	// Feed mic samples into VOX when active
	$effect(() => {
		if (!voxActive || !micSamples) return;
		const detected = voxDetector.process(micSamples);
		voxDetecting = detected;
		if (detected !== ptt) {
			controlWs?.send({ type: 'ptt', active: detected });
		}
	});

	// When VOX is turned off, ensure PTT is released
	$effect(() => {
		if (!voxActive) {
			voxDetector.reset();
			voxDetecting = false;
		}
	});

	function toggleVox() {
		voxActive = !voxActive;
		if (!voxActive && ptt) {
			// Release PTT if VOX was holding it
			controlWs?.send({ type: 'ptt', active: false });
		}
	}

	// Support press-and-hold: send PTT on pointerdown, release on pointerup
	function onPointerDown(e: PointerEvent) {
		(e.target as HTMLElement).setPointerCapture(e.pointerId);
		if (!ptt) controlWs?.send({ type: 'ptt', active: true });
	}

	function onPointerUp() {
		if (ptt) controlWs?.send({ type: 'ptt', active: false });
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === ' ' || e.key === 'Enter') {
			e.preventDefault();
			controlWs?.send({ type: 'ptt', active: !ptt });
		}
	}
</script>

<div class="ptt-wrap">
	<button
		class="ptt-btn"
		class:active={ptt}
		onpointerdown={onPointerDown}
		onpointerup={onPointerUp}
		onkeydown={onKeydown}
		aria-label={ptt ? 'Transmitting — press to release PTT' : 'Push to Talk — press and hold to transmit'}
		aria-pressed={ptt}
	>
		{ptt ? 'TX' : 'PTT'}
	</button>

	{#if ptt}
		<span class="tx-indicator" aria-live="assertive" aria-atomic="true">TRANSMITTING</span>
	{/if}

	<div class="vox-row">
		<button
			class="vox-btn"
			class:active={voxActive}
			onclick={toggleVox}
			aria-pressed={voxActive}
			aria-label={voxActive ? 'Disable VOX' : 'Enable VOX — voice-operated transmit'}
		>
			VOX
		</button>
		{#if voxActive}
			<span
				class="vox-indicator"
				class:detecting={voxDetecting}
				aria-live="polite"
				aria-label={voxDetecting ? 'VOX: voice detected' : 'VOX: listening'}
			>
				{voxDetecting ? 'VOICE' : 'QUIET'}
			</span>
		{/if}
	</div>
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

	.ptt-btn:focus-visible {
		outline: 3px solid #4a9eff;
		outline-offset: 3px;
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

	.vox-row {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.vox-btn {
		padding: 4px 12px;
		font-size: 0.78rem;
		font-weight: 700;
		background: #1a1a1a;
		border: 1px solid #444;
		border-radius: 4px;
		color: #aaa;
		cursor: pointer;
		letter-spacing: 0.06em;
		transition: background 0.1s, border-color 0.1s, color 0.1s;
	}

	.vox-btn:hover:not(.active) {
		border-color: #666;
		color: #ccc;
	}

	.vox-btn.active {
		background: #1b3a1b;
		border-color: #4caf50;
		color: #4caf50;
	}

	.vox-btn:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
	}

	.vox-indicator {
		font-size: 0.72rem;
		font-weight: 700;
		color: #555;
		letter-spacing: 0.08em;
		transition: color 0.1s;
	}

	.vox-indicator.detecting {
		color: #4caf50;
		animation: pulse 0.6s ease-in-out infinite alternate;
	}

	@keyframes blink {
		0%, 100% { opacity: 1; }
		50% { opacity: 0; }
	}

	@keyframes pulse {
		from { opacity: 0.6; }
		to   { opacity: 1; }
	}

	@media (prefers-reduced-motion: reduce) {
		.ptt-btn {
			transition: none;
		}
		.tx-indicator {
			animation: none;
		}
		.vox-indicator.detecting {
			animation: none;
		}
	}
</style>
