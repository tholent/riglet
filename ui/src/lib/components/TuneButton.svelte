<script lang="ts">
	import type { ControlWebSocket } from '$lib/websocket.js';

	interface Props {
		ptt: boolean;
		tuning: boolean;
		tunerEnabled: boolean;
		swr: number;
		controlWs: ControlWebSocket | null;
	}
	let { ptt, tuning, tunerEnabled, swr, controlWs }: Props = $props();

	const METHOD_KEY = 'riglet:tuneMethod';
	const DURATION_KEY = 'riglet:tuneDuration';

	function loadMethod(): 'builtin' | 'external' {
		try {
			const v = localStorage.getItem(METHOD_KEY);
			return v === 'external' ? 'external' : 'builtin';
		} catch { return 'builtin'; }
	}

	function loadDuration(): number {
		try {
			const v = localStorage.getItem(DURATION_KEY);
			const n = v ? parseInt(v, 10) : 5;
			return [3, 5, 10].includes(n) ? n : 5;
		} catch { return 5; }
	}

	let tuneMethod: 'builtin' | 'external' = $state(loadMethod());
	let externalDuration: number = $state(loadDuration());

	function setMethod(m: 'builtin' | 'external') {
		tuneMethod = m;
		try { localStorage.setItem(METHOD_KEY, m); } catch { /* ignore */ }
	}

	function setDuration(d: number) {
		externalDuration = d;
		try { localStorage.setItem(DURATION_KEY, String(d)); } catch { /* ignore */ }
	}

	function swrColor(value: number): string {
		if (value < 1.5) return '#4caf50';   // green
		if (value < 2.5) return '#ffc107';   // amber
		if (value < 3.5) return '#ff9800';   // orange
		return '#f44336';                     // red
	}

	function startTune() {
		if (ptt || tuning) return;
		controlWs?.send({
			type: 'tune_start',
			method: tuneMethod,
			duration: externalDuration,
		});
	}

	function stopTune() {
		controlWs?.send({ type: 'tune_stop' });
	}

	function toggleTuner() {
		controlWs?.send({ type: tunerEnabled ? 'tuner_disable' : 'tuner_enable' });
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && tuning) {
			e.preventDefault();
			stopTune();
		} else if ((e.key === ' ' || e.key === 'Enter') && !tuning) {
			e.preventDefault();
			startTune();
		}
	}
</script>

<div class="tune-wrap">
	<!-- Main tune button -->
	<button
		class="tune-btn"
		class:active={tuning}
		class:disabled={ptt}
		onclick={tuning ? stopTune : startTune}
		onkeydown={onKeydown}
		disabled={ptt}
		aria-label={tuning ? 'Tuning in progress — press to abort' : 'Start antenna tune cycle'}
		aria-pressed={tuning}
		title={ptt ? 'Cannot tune while transmitting' : tuning ? 'Click to abort tune' : 'Start tune'}
	>
		{#if tuning}
			<span class="spinner" aria-hidden="true"></span>
			<span class="btn-label">TUNING</span>
		{:else}
			<span class="btn-label">TUNE</span>
		{/if}
	</button>

	<!-- Controls row: method + ATU toggle -->
	<div class="tune-controls">
		<div class="method-toggle" role="group" aria-label="Tune method">
			<button
				class="method-btn"
				class:active={tuneMethod === 'builtin'}
				onclick={() => setMethod('builtin')}
				aria-pressed={tuneMethod === 'builtin'}
				aria-label="Built-in ATU tune"
				title="Built-in ATU tune"
			>INT</button>
			<button
				class="method-btn"
				class:active={tuneMethod === 'external'}
				onclick={() => setMethod('external')}
				aria-pressed={tuneMethod === 'external'}
				aria-label="External tuner via PTT carrier"
				title="External tuner via PTT carrier"
			>EXT</button>
		</div>

		<button
			class="atu-btn"
			class:active={tunerEnabled}
			onclick={toggleTuner}
			aria-pressed={tunerEnabled}
			aria-label={tunerEnabled ? 'Disable ATU' : 'Enable ATU'}
			title={tunerEnabled ? 'ATU enabled — click to disable' : 'ATU disabled — click to enable'}
		>ATU</button>
	</div>

	<!-- SWR readout: visible during TX or tuning -->
	{#if tuning || ptt}
		<div
			class="swr-readout"
			style="color: {swrColor(swr)}"
			aria-label={`SWR ${swr.toFixed(1)} to 1`}
			aria-live="polite"
		>
			{swr.toFixed(1)}:1
		</div>
	{/if}

	<!-- Duration selector (external mode only) -->
	{#if tuneMethod === 'external'}
		<div class="duration-select" role="group" aria-label="Tune duration">
			{#each [3, 5, 10] as d}
				<button
					class="dur-btn"
					class:active={externalDuration === d}
					onclick={() => setDuration(d)}
					aria-pressed={externalDuration === d}
					aria-label={`${d} second tune duration`}
				>{d}s</button>
			{/each}
		</div>
	{/if}
</div>

<style>
	.tune-wrap {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 6px;
	}

	.tune-btn {
		width: 72px;
		height: 72px;
		border-radius: 50%;
		border: 3px solid #d4a017;
		background: #1a1a1a;
		color: #d4a017;
		font-size: 0.85rem;
		font-weight: 700;
		cursor: pointer;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 3px;
		transition: background 0.15s, border-color 0.15s, color 0.15s;
		touch-action: none;
		user-select: none;
		letter-spacing: 0.06em;
	}

	.tune-btn:hover:not(.active):not(.disabled):not(:disabled) {
		border-color: #f0c040;
		color: #f0c040;
		background: #1e1a00;
	}

	.tune-btn:focus-visible {
		outline: 3px solid #4a9eff;
		outline-offset: 3px;
	}

	.tune-btn.active {
		background: #3a2800;
		border-color: #f0c040;
		color: #f0c040;
		box-shadow: 0 0 14px rgba(212, 160, 23, 0.5);
		animation: tune-pulse 1s ease-in-out infinite alternate;
	}

	.tune-btn.disabled,
	.tune-btn:disabled {
		opacity: 0.35;
		cursor: not-allowed;
		pointer-events: none;
	}

	.btn-label {
		font-size: 0.8rem;
		font-weight: 700;
		letter-spacing: 0.08em;
	}

	/* Spinner ring */
	.spinner {
		width: 14px;
		height: 14px;
		border: 2px solid rgba(240, 192, 64, 0.3);
		border-top-color: #f0c040;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
		flex-shrink: 0;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	@keyframes tune-pulse {
		from { box-shadow: 0 0 8px rgba(212, 160, 23, 0.4); }
		to   { box-shadow: 0 0 20px rgba(212, 160, 23, 0.7); }
	}

	/* Controls row */
	.tune-controls {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	/* Method toggle pills */
	.method-toggle {
		display: flex;
		border-radius: 4px;
		overflow: hidden;
		border: 1px solid #444;
	}

	.method-btn {
		padding: 2px 6px;
		font-size: 0.65rem;
		font-weight: 700;
		background: #111;
		border: none;
		color: #666;
		cursor: pointer;
		letter-spacing: 0.04em;
		transition: background 0.1s, color 0.1s;
	}

	.method-btn + .method-btn {
		border-left: 1px solid #444;
	}

	.method-btn.active {
		background: #1a2a1a;
		color: #4caf50;
	}

	.method-btn:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 1px;
	}

	/* ATU toggle */
	.atu-btn {
		padding: 3px 8px;
		font-size: 0.7rem;
		font-weight: 700;
		background: #1a1a1a;
		border: 1px solid #444;
		border-radius: 4px;
		color: #666;
		cursor: pointer;
		letter-spacing: 0.06em;
		transition: background 0.1s, border-color 0.1s, color 0.1s;
	}

	.atu-btn:hover:not(.active) {
		border-color: #666;
		color: #aaa;
	}

	.atu-btn.active {
		background: #1b3a1b;
		border-color: #4caf50;
		color: #4caf50;
	}

	.atu-btn:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
	}

	/* SWR readout */
	.swr-readout {
		font-family: monospace;
		font-size: 0.82rem;
		font-weight: 700;
		letter-spacing: 0.04em;
		transition: color 0.2s;
	}

	/* Duration selector */
	.duration-select {
		display: flex;
		gap: 3px;
	}

	.dur-btn {
		padding: 2px 6px;
		font-size: 0.65rem;
		font-weight: 700;
		background: #111;
		border: 1px solid #444;
		border-radius: 3px;
		color: #666;
		cursor: pointer;
		transition: background 0.1s, color 0.1s, border-color 0.1s;
	}

	.dur-btn.active {
		background: #1a2a3a;
		border-color: #4a9eff;
		color: #4a9eff;
	}

	.dur-btn:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 1px;
	}

	@media (prefers-reduced-motion: reduce) {
		.tune-btn.active {
			animation: none;
		}
		.spinner {
			animation: none;
		}
	}
</style>
