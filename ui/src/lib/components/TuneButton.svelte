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

	const METHOD_KEY   = 'riglet:tuneMethod';
	const DURATION_KEY = 'riglet:tuneDuration';

	function loadMethod(): 'builtin' | 'external' {
		try { const v = localStorage.getItem(METHOD_KEY); return v === 'external' ? 'external' : 'builtin'; }
		catch { return 'builtin'; }
	}
	function loadDuration(): number {
		try { const v = localStorage.getItem(DURATION_KEY); const n = v ? parseInt(v, 10) : 5; return [3, 5, 10].includes(n) ? n : 5; }
		catch { return 5; }
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

	function swrColor(v: number): string {
		if (v < 1.5) return '#4caf50';
		if (v < 2.5) return '#ffc107';
		if (v < 3.5) return '#ff9800';
		return '#f44336';
	}

	function startTune() {
		if (ptt || tuning) return;
		controlWs?.send({ type: 'tune_start', method: tuneMethod, duration: externalDuration });
	}
	function stopTune() {
		controlWs?.send({ type: 'tune_stop' });
	}
	function toggleTuner() {
		controlWs?.send({ type: tunerEnabled ? 'tuner_disable' : 'tuner_enable' });
	}
	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && tuning) { e.preventDefault(); stopTune(); }
		else if ((e.key === ' ' || e.key === 'Enter') && !tuning) { e.preventDefault(); startTune(); }
	}
</script>

<div class="tune-col">
	<span class="col-label">TUNE</span>

	<!-- Main tune trigger -->
	<button
		class="tune-btn"
		class:active={tuning}
		onclick={tuning ? stopTune : startTune}
		onkeydown={onKeydown}
		disabled={ptt && !tuning}
		aria-label={tuning ? 'Tuning — press to abort' : 'Start tune cycle'}
		aria-pressed={tuning}
		title={ptt && !tuning ? 'Cannot tune while transmitting' : tuning ? 'Click to abort' : 'Start tune'}
	>
		{#if tuning}
			<span class="spinner" aria-hidden="true"></span>
		{:else}
			<span class="tune-icon" aria-hidden="true">⟳</span>
		{/if}
	</button>

	<!-- ATU enable/disable -->
	<button
		class="circle-btn"
		class:active={tunerEnabled}
		onclick={toggleTuner}
		aria-pressed={tunerEnabled}
		aria-label={tunerEnabled ? 'Disable ATU' : 'Enable ATU'}
		title={tunerEnabled ? 'ATU enabled' : 'ATU disabled'}
	>ATU</button>

	<!-- Method: INT / EXT -->
	<div class="seg-ctrl" role="group" aria-label="Tune method">
		<button
			class="seg-btn"
			class:active={tuneMethod === 'builtin'}
			onclick={() => setMethod('builtin')}
			aria-pressed={tuneMethod === 'builtin'}
			title="Built-in ATU tune"
		>INT</button><button
			class="seg-btn"
			class:active={tuneMethod === 'external'}
			onclick={() => setMethod('external')}
			aria-pressed={tuneMethod === 'external'}
			title="External tuner via PTT carrier"
		>EXT</button>
	</div>

	<!-- Duration pills (external mode only) -->
	{#if tuneMethod === 'external'}
		<div class="dur-row" role="group" aria-label="Tune duration">
			{#each [3, 5, 10] as d}
				<button
					class="dur-btn"
					class:active={externalDuration === d}
					onclick={() => setDuration(d)}
					aria-pressed={externalDuration === d}
					aria-label="{d}s tune duration"
				>{d}s</button>
			{/each}
		</div>
	{/if}

	<!-- SWR readout: visible during TX or tuning -->
	{#if tuning || ptt}
		<div
			class="swr"
			style="color: {swrColor(swr)}"
			aria-label="SWR {swr.toFixed(1)} to 1"
			aria-live="polite"
		>{swr.toFixed(1)}:1</div>
	{:else}
		<div class="swr swr-idle" aria-hidden="true">–:–</div>
	{/if}
</div>

<style>
	.tune-col {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 6px;
		padding: 8px 10px;
		border-left: 1px solid #222;
	}

	/* Panel section label — matches TxDspPanel column header convention */
	.col-label {
		font-size: 0.55rem;
		font-family: monospace;
		font-weight: 700;
		letter-spacing: 0.12em;
		color: #444;
		text-transform: uppercase;
		user-select: none;
	}

	/* ── Tune trigger button — amber, larger than circle-btn ── */
	.tune-btn {
		width: 52px;
		height: 52px;
		border-radius: 50%;
		border: 1px solid #5a4000;
		background: #252010;
		color: #a07010;
		font-size: 1.1rem;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		transition: background 0.12s, border-color 0.12s, color 0.12s, box-shadow 0.12s;
		user-select: none;
	}

	.tune-btn:hover:not(:disabled):not(.active) {
		border-color: #c08820;
		color: #d4a020;
		background: #2a2008;
	}

	.tune-btn.active {
		border-color: #d4a020;
		background: #2a1e00;
		color: #f0c040;
		box-shadow: 0 0 10px rgba(212, 160, 32, 0.45);
		animation: tune-pulse 1.1s ease-in-out infinite alternate;
	}

	.tune-btn:disabled {
		opacity: 0.3;
		cursor: not-allowed;
	}

	.tune-btn:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 3px;
	}

	.tune-icon {
		font-size: 1.3rem;
		line-height: 1;
	}

	/* ── Shared small circle button (ATU) ── */
	.circle-btn {
		width: 36px;
		height: 36px;
		border-radius: 50%;
		border: 1px solid #3a3a3a;
		background: #252525;
		color: #777;
		font-size: 0.58rem;
		font-weight: 700;
		letter-spacing: 0.04em;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		transition: background 0.1s, border-color 0.1s, color 0.1s;
	}

	.circle-btn:hover:not(.active) {
		border-color: #555;
		background: #2e2e2e;
		color: #ccc;
	}

	.circle-btn.active {
		background: #0284c7;
		border-color: #0ea5e9;
		color: #fff;
	}

	.circle-btn:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
	}

	/* ── Segmented INT/EXT control ── */
	.seg-ctrl {
		display: flex;
		border-radius: 3px;
		overflow: hidden;
		border: 1px solid #333;
	}

	.seg-btn {
		padding: 2px 5px;
		font-size: 0.58rem;
		font-weight: 700;
		letter-spacing: 0.04em;
		background: #1a1a1a;
		border: none;
		color: #555;
		cursor: pointer;
		transition: background 0.1s, color 0.1s;
	}

	.seg-btn + .seg-btn {
		border-left: 1px solid #333;
	}

	.seg-btn.active {
		background: #1a2a1a;
		color: #4caf50;
	}

	.seg-btn:focus-visible {
		outline: 1px solid #4a9eff;
		outline-offset: 1px;
	}

	/* ── Duration pills ── */
	.dur-row {
		display: flex;
		gap: 2px;
	}

	.dur-btn {
		padding: 2px 5px;
		font-size: 0.58rem;
		font-weight: 700;
		background: #1a1a1a;
		border: 1px solid #333;
		border-radius: 3px;
		color: #555;
		cursor: pointer;
		transition: background 0.1s, color 0.1s, border-color 0.1s;
	}

	.dur-btn.active {
		background: #1a2030;
		border-color: #4a9eff;
		color: #4a9eff;
	}

	.dur-btn:focus-visible {
		outline: 1px solid #4a9eff;
		outline-offset: 1px;
	}

	/* ── SWR readout ── */
	.swr {
		font-family: monospace;
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.04em;
		transition: color 0.2s;
	}

	.swr-idle {
		color: #333;
	}

	/* ── Animations ── */
	@keyframes tune-pulse {
		from { box-shadow: 0 0 6px rgba(212, 160, 32, 0.35); }
		to   { box-shadow: 0 0 16px rgba(212, 160, 32, 0.65); }
	}

	@media (prefers-reduced-motion: reduce) {
		.tune-btn.active { animation: none; }
		.spinner { animation: none; }
	}

	/* Spinner for active tuning state */
	.spinner {
		width: 16px;
		height: 16px;
		border: 2px solid rgba(240, 192, 64, 0.25);
		border-top-color: #f0c040;
		border-radius: 50%;
		animation: spin 0.7s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}
</style>
