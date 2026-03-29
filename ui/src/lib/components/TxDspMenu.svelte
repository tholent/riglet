<script lang="ts">
	import type { TxDspChain, CompressorPreset } from '$lib/audio/tx-dsp-chain.js';
	import { createEventDispatcher, onDestroy } from 'svelte';

	interface Props {
		txDspChain: TxDspChain | null;
		open: boolean;
	}
	let { txDspChain, open = $bindable(false) }: Props = $props();

	const dispatch = createEventDispatcher<{ change: { param: string; value: unknown } }>();

	// ── Filter state ─────────────────────────────────────────────────
	let hpEnabled = $state(false);
	let hpFreq = $state(150);
	let lpEnabled = $state(false);
	let lpFreq = $state(2800);

	// ── EQ state ─────────────────────────────────────────────────────
	let eqEnabled = $state(false);
	let eqBass = $state(0);
	let eqMid = $state(0);
	let eqTreble = $state(0);

	// ── Compressor state ─────────────────────────────────────────────
	let compEnabled = $state(false);
	let compPreset = $state<CompressorPreset>('medium');
	let compThreshold = $state(-24);
	let compRatio = $state(4);
	let compAttack = $state(0.003);
	let compRelease = $state(0.25);

	// ── Limiter state ─────────────────────────────────────────────────
	let limEnabled = $state(false);
	let limThreshold = $state(-3);

	// ── Gate state ────────────────────────────────────────────────────
	let gateEnabled = $state(false);
	let gateThreshold = $state(-60);

	// ── Click-outside + Escape ────────────────────────────────────────
	let menuEl = $state<HTMLDivElement | undefined>(undefined);

	function onClickOutside(e: MouseEvent): void {
		if (open && menuEl && !menuEl.contains(e.target as Node)) {
			open = false;
		}
	}

	function closeOnEscape(e: KeyboardEvent): void {
		if (e.key === 'Escape') open = false;
	}

	$effect(() => {
		if (open) {
			document.addEventListener('click', onClickOutside, true);
		} else {
			document.removeEventListener('click', onClickOutside, true);
		}
		return () => document.removeEventListener('click', onClickOutside, true);
	});

	onDestroy(() => {
		document.removeEventListener('click', onClickOutside, true);
	});

	// ── Helpers ───────────────────────────────────────────────────────

	function emit(param: string, value: unknown): void {
		dispatch('change', { param, value });
	}

	// ── Highpass ──────────────────────────────────────────────────────

	function onHpToggle(): void {
		hpEnabled = !hpEnabled;
		txDspChain?.enableHighpass(hpEnabled);
		if (hpEnabled) txDspChain?.setHighpass(hpFreq);
		emit('hp_enabled', hpEnabled);
	}

	function onHpFreq(): void {
		if (hpEnabled) txDspChain?.setHighpass(hpFreq);
		emit('hp_freq', hpFreq);
	}

	// ── Lowpass ───────────────────────────────────────────────────────

	function onLpToggle(): void {
		lpEnabled = !lpEnabled;
		txDspChain?.enableLowpass(lpEnabled);
		if (lpEnabled) txDspChain?.setLowpass(lpFreq);
		emit('lp_enabled', lpEnabled);
	}

	function onLpFreq(): void {
		if (lpEnabled) txDspChain?.setLowpass(lpFreq);
		emit('lp_freq', lpFreq);
	}

	// ── EQ ────────────────────────────────────────────────────────────

	function onEqToggle(): void {
		eqEnabled = !eqEnabled;
		txDspChain?.enableEq(eqEnabled);
		if (eqEnabled) {
			txDspChain?.setBass(eqBass);
			txDspChain?.setMid(eqMid);
			txDspChain?.setTreble(eqTreble);
		}
		emit('eq_enabled', eqEnabled);
	}

	function onEqBass(): void {
		if (eqEnabled) txDspChain?.setBass(eqBass);
		emit('eq_bass', eqBass);
	}

	function onEqMid(): void {
		if (eqEnabled) txDspChain?.setMid(eqMid);
		emit('eq_mid', eqMid);
	}

	function onEqTreble(): void {
		if (eqEnabled) txDspChain?.setTreble(eqTreble);
		emit('eq_treble', eqTreble);
	}

	// ── Compressor ────────────────────────────────────────────────────

	function onCompToggle(): void {
		compEnabled = !compEnabled;
		txDspChain?.enableCompressor(compEnabled);
		if (compEnabled && compPreset !== 'manual') {
			txDspChain?.setCompressorPreset(compPreset);
		}
		emit('comp_enabled', compEnabled);
	}

	function onCompPreset(preset: CompressorPreset): void {
		compPreset = preset;
		if (compEnabled) txDspChain?.setCompressorPreset(preset);
		emit('comp_preset', preset);
	}

	function onCompManual(): void {
		compPreset = 'manual';
		if (compEnabled) txDspChain?.setCompressor(compThreshold, compRatio, compAttack, compRelease);
		emit('comp_manual', { compThreshold, compRatio, compAttack, compRelease });
	}

	// ── Limiter ───────────────────────────────────────────────────────

	function onLimToggle(): void {
		limEnabled = !limEnabled;
		txDspChain?.enableLimiter(limEnabled);
		emit('lim_enabled', limEnabled);
	}

	function onLimThreshold(): void {
		txDspChain?.setLimiterThreshold(limThreshold);
		emit('lim_threshold', limThreshold);
	}

	// ── Gate ──────────────────────────────────────────────────────────

	function onGateToggle(): void {
		gateEnabled = !gateEnabled;
		txDspChain?.enableGate(gateEnabled);
		emit('gate_enabled', gateEnabled);
	}

	function onGateThreshold(): void {
		txDspChain?.setGateThreshold(gateThreshold);
		emit('gate_threshold', gateThreshold);
	}
</script>

{#if open}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="tx-dsp-panel"
		role="dialog"
		aria-label="TX DSP controls"
		tabindex="-1"
		bind:this={menuEl}
		onkeydown={closeOnEscape}
	>

		<!-- ── Filters ─────────────────────────────── -->
		<details>
			<summary class="section-header">Filters</summary>
			<div class="section-body">
				<div class="toggle-row">
					<label>
						<input type="checkbox" bind:checked={hpEnabled} onchange={onHpToggle} />
						Highpass
					</label>
				</div>
				<div class="slider-row" class:disabled={!hpEnabled}>
					<label for="hp-freq">Freq (Hz)</label>
					<input
						id="hp-freq"
						type="range"
						min="50"
						max="500"
						step="10"
						bind:value={hpFreq}
						disabled={!hpEnabled}
						oninput={onHpFreq}
						aria-label="Highpass frequency"
					/>
					<span class="val">{hpFreq}</span>
				</div>

				<div class="toggle-row">
					<label>
						<input type="checkbox" bind:checked={lpEnabled} onchange={onLpToggle} />
						Lowpass
					</label>
				</div>
				<div class="slider-row" class:disabled={!lpEnabled}>
					<label for="lp-freq">Freq (Hz)</label>
					<input
						id="lp-freq"
						type="range"
						min="1500"
						max="5000"
						step="50"
						bind:value={lpFreq}
						disabled={!lpEnabled}
						oninput={onLpFreq}
						aria-label="Lowpass frequency"
					/>
					<span class="val">{lpFreq}</span>
				</div>
			</div>
		</details>

		<!-- ── EQ ─────────────────────────────────── -->
		<details>
			<summary class="section-header">
				EQ
				<label class="inline-toggle">
					<input onclick={(e) => e.stopPropagation()} type="checkbox" bind:checked={eqEnabled} onchange={onEqToggle} />
					{eqEnabled ? 'On' : 'Off'}
				</label>
			</summary>
			<div class="section-body" class:disabled={!eqEnabled}>
				<div class="slider-row">
					<label for="eq-bass">Bass (dB)</label>
					<input
						id="eq-bass"
						type="range"
						min="-20"
						max="20"
						step="1"
						bind:value={eqBass}
						disabled={!eqEnabled}
						oninput={onEqBass}
						aria-label="Bass gain"
					/>
					<span class="val">{eqBass > 0 ? '+' : ''}{eqBass}</span>
				</div>
				<div class="slider-row">
					<label for="eq-mid">Mid (dB)</label>
					<input
						id="eq-mid"
						type="range"
						min="-20"
						max="20"
						step="1"
						bind:value={eqMid}
						disabled={!eqEnabled}
						oninput={onEqMid}
						aria-label="Mid gain"
					/>
					<span class="val">{eqMid > 0 ? '+' : ''}{eqMid}</span>
				</div>
				<div class="slider-row">
					<label for="eq-treble">Treble (dB)</label>
					<input
						id="eq-treble"
						type="range"
						min="-20"
						max="20"
						step="1"
						bind:value={eqTreble}
						disabled={!eqEnabled}
						oninput={onEqTreble}
						aria-label="Treble gain"
					/>
					<span class="val">{eqTreble > 0 ? '+' : ''}{eqTreble}</span>
				</div>
			</div>
		</details>

		<!-- ── Compressor ─────────────────────────── -->
		<details>
			<summary class="section-header">
				Compressor
				<label class="inline-toggle">
					<input onclick={(e) => e.stopPropagation()} type="checkbox" bind:checked={compEnabled} onchange={onCompToggle} />
					{compEnabled ? 'On' : 'Off'}
				</label>
			</summary>
			<div class="section-body" class:disabled={!compEnabled}>
				<div class="preset-row">
					{#each (['light', 'medium', 'heavy', 'manual'] as const) as preset}
						<button
							class="preset-pill"
							class:active={compPreset === preset}
							disabled={!compEnabled}
							onclick={() => onCompPreset(preset)}
							aria-pressed={compPreset === preset}
						>{preset}</button>
					{/each}
				</div>
				{#if compPreset === 'manual'}
					<div class="slider-row">
						<label for="comp-threshold">Threshold</label>
						<input
							id="comp-threshold"
							type="range"
							min="-60"
							max="0"
							step="1"
							bind:value={compThreshold}
							disabled={!compEnabled}
							oninput={onCompManual}
							aria-label="Compressor threshold in dB"
						/>
						<span class="val">{compThreshold} dB</span>
					</div>
					<div class="slider-row">
						<label for="comp-ratio">Ratio</label>
						<input
							id="comp-ratio"
							type="range"
							min="1"
							max="20"
							step="0.5"
							bind:value={compRatio}
							disabled={!compEnabled}
							oninput={onCompManual}
							aria-label="Compressor ratio"
						/>
						<span class="val">{compRatio}:1</span>
					</div>
					<div class="slider-row">
						<label for="comp-attack">Attack</label>
						<input
							id="comp-attack"
							type="range"
							min="0.001"
							max="0.1"
							step="0.001"
							bind:value={compAttack}
							disabled={!compEnabled}
							oninput={onCompManual}
							aria-label="Compressor attack in seconds"
						/>
						<span class="val">{(compAttack * 1000).toFixed(0)} ms</span>
					</div>
					<div class="slider-row">
						<label for="comp-release">Release</label>
						<input
							id="comp-release"
							type="range"
							min="0.01"
							max="1"
							step="0.01"
							bind:value={compRelease}
							disabled={!compEnabled}
							oninput={onCompManual}
							aria-label="Compressor release in seconds"
						/>
						<span class="val">{(compRelease * 1000).toFixed(0)} ms</span>
					</div>
				{/if}
			</div>
		</details>

		<!-- ── Limiter ────────────────────────────── -->
		<details>
			<summary class="section-header">
				Limiter
				<label class="inline-toggle">
					<input onclick={(e) => e.stopPropagation()} type="checkbox" bind:checked={limEnabled} onchange={onLimToggle} />
					{limEnabled ? 'On' : 'Off'}
				</label>
			</summary>
			<div class="section-body" class:disabled={!limEnabled}>
				<div class="slider-row">
					<label for="lim-threshold">Threshold</label>
					<input
						id="lim-threshold"
						type="range"
						min="-20"
						max="0"
						step="1"
						bind:value={limThreshold}
						disabled={!limEnabled}
						oninput={onLimThreshold}
						aria-label="Limiter threshold in dBFS"
					/>
					<span class="val">{limThreshold} dB</span>
				</div>
			</div>
		</details>

		<!-- ── Gate ──────────────────────────────── -->
		<details>
			<summary class="section-header">
				Gate
				<label class="inline-toggle">
					<input onclick={(e) => e.stopPropagation()} type="checkbox" bind:checked={gateEnabled} onchange={onGateToggle} />
					{gateEnabled ? 'On' : 'Off'}
				</label>
			</summary>
			<div class="section-body" class:disabled={!gateEnabled}>
				<div class="slider-row">
					<label for="gate-threshold">Threshold</label>
					<input
						id="gate-threshold"
						type="range"
						min="-100"
						max="0"
						step="1"
						bind:value={gateThreshold}
						disabled={!gateEnabled}
						oninput={onGateThreshold}
						aria-label="Gate threshold in dBFS"
					/>
					<span class="val">{gateThreshold} dB</span>
				</div>
			</div>
		</details>

	</div>
{/if}

<style>
	.tx-dsp-panel {
		position: absolute;
		bottom: calc(100% + 6px);
		left: 0;
		z-index: 100;
		width: 280px;
		background: #141414;
		border: 1px solid #333;
		border-radius: 6px;
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
		overflow: hidden;
	}

	details {
		border-bottom: 1px solid #222;
	}

	details:last-child {
		border-bottom: none;
	}

	.section-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 6px 10px;
		background: #1a1a1a;
		cursor: pointer;
		list-style: none;
		user-select: none;
		font-size: 0.78rem;
		font-weight: 600;
		letter-spacing: 0.04em;
		color: #bbb;
	}

	.section-header::-webkit-details-marker {
		display: none;
	}

	.section-header:hover {
		background: #222;
	}

	.section-body {
		padding: 8px 10px;
		background: #111;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.section-body.disabled {
		opacity: 0.5;
		pointer-events: none;
	}

	.toggle-row {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 0.78rem;
		color: #bbb;
	}

	.toggle-row label {
		display: flex;
		align-items: center;
		gap: 5px;
		cursor: pointer;
	}

	.slider-row {
		display: grid;
		grid-template-columns: 80px 1fr 52px;
		align-items: center;
		gap: 6px;
	}

	.slider-row.disabled {
		opacity: 0.4;
		pointer-events: none;
	}

	.slider-row label {
		font-size: 0.72rem;
		color: #999;
		white-space: nowrap;
	}

	input[type='range'] {
		width: 100%;
		accent-color: #0ea5e9;
	}

	.val {
		font-size: 0.7rem;
		font-family: 'Courier New', monospace;
		color: #aaa;
		text-align: right;
		white-space: nowrap;
	}

	.inline-toggle {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		font-size: 0.7rem;
		font-weight: 400;
		color: #888;
		cursor: pointer;
	}

	.preset-row {
		display: flex;
		gap: 4px;
		flex-wrap: wrap;
	}

	.preset-pill {
		padding: 2px 8px;
		border-radius: 99px;
		border: 1px solid #444;
		background: #1a1a1a;
		color: #888;
		font-size: 0.7rem;
		font-weight: 600;
		cursor: pointer;
		transition: background 0.1s, border-color 0.1s, color 0.1s;
	}

	.preset-pill:hover:not(:disabled) {
		border-color: #666;
		color: #ccc;
	}

	.preset-pill.active {
		background: #0284c7;
		border-color: #0ea5e9;
		color: #fff;
	}

	.preset-pill:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.preset-pill:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
	}

	@media (prefers-reduced-motion: reduce) {
		.preset-pill {
			transition: none;
		}
	}
</style>
