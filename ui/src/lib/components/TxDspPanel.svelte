<script lang="ts">
	import type { TxDspChain, CompressorPreset, LimiterPreset } from '$lib/audio/tx-dsp-chain.js';
	import { createEventDispatcher, onDestroy } from 'svelte';
	import Knob from './Knob.svelte';

	interface Props {
		txDspChain: TxDspChain | null;
		txGain: number;
		onTxGainChange: (v: number) => void;
	}
	let { txDspChain, txGain, onTxGainChange }: Props = $props();

	const dispatch = createEventDispatcher<{ change: { param: string; value: unknown } }>();

	function emit(param: string, value: unknown): void {
		dispatch('change', { param, value });
	}

	// ── Filter popovers ───────────────────────────────────────────────
	type FilterKey = 'hp' | 'lp' | 'lim' | 'comp';
	let openFilter = $state<FilterKey | null>(null);

	let hpEl    = $state<HTMLButtonElement | undefined>(undefined);
	let lpEl    = $state<HTMLButtonElement | undefined>(undefined);
	let limEl   = $state<HTMLButtonElement | undefined>(undefined);
	let compEl  = $state<HTMLButtonElement | undefined>(undefined);
	let popoverEl = $state<HTMLDivElement | undefined>(undefined);

	function togglePopover(f: FilterKey): void {
		openFilter = openFilter === f ? null : f;
	}

	function getAnchor(): HTMLButtonElement | null {
		if (openFilter === 'hp')   return hpEl   ?? null;
		if (openFilter === 'lp')   return lpEl   ?? null;
		if (openFilter === 'lim')  return limEl  ?? null;
		if (openFilter === 'comp') return compEl ?? null;
		return null;
	}

	let posStyle = $derived.by(() => {
		if (!openFilter) return '';
		const anchor = getAnchor();
		if (!anchor) return '';
		const rect = anchor.getBoundingClientRect();
		return `position:fixed; top:${rect.bottom + 4}px; left:${rect.left}px; z-index:200;`;
	});

	function onClickOutside(e: MouseEvent): void {
		if (!openFilter) return;
		const target = e.target as Node;
		const anchor = getAnchor();
		if (popoverEl && !popoverEl.contains(target) && anchor && !anchor.contains(target)) {
			openFilter = null;
		}
	}

	function onPopoverKeydown(e: KeyboardEvent): void {
		if (e.key === 'Escape') openFilter = null;
	}

	$effect(() => {
		if (openFilter) {
			document.addEventListener('click', onClickOutside, true);
		} else {
			document.removeEventListener('click', onClickOutside, true);
		}
		return () => document.removeEventListener('click', onClickOutside, true);
	});

	onDestroy(() => {
		document.removeEventListener('click', onClickOutside, true);
	});

	// ── Filters ───────────────────────────────────────────────────────
	let hpEnabled = $state(false);
	let hpFreq    = $state(150);
	let lpEnabled = $state(false);
	let lpFreq    = $state(2800);

	function onHpEnabled(): void {
		txDspChain?.enableHighpass(hpEnabled);
		if (hpEnabled) txDspChain?.setHighpass(hpFreq);
		emit('hp_enabled', hpEnabled);
	}
	function onHpFreq(): void {
		if (hpEnabled) txDspChain?.setHighpass(hpFreq);
		emit('hp_freq', hpFreq);
	}

	function onLpEnabled(): void {
		txDspChain?.enableLowpass(lpEnabled);
		if (lpEnabled) txDspChain?.setLowpass(lpFreq);
		emit('lp_enabled', lpEnabled);
	}
	function onLpFreq(): void {
		if (lpEnabled) txDspChain?.setLowpass(lpFreq);
		emit('lp_freq', lpFreq);
	}

	// ── EQ ────────────────────────────────────────────────────────────
	let eqBass   = $state(0);
	let eqMid    = $state(0);
	let eqTreble = $state(0);

	// EQ is always enabled
	$effect(() => {
		if (txDspChain) {
			txDspChain.enableEq(true);
			txDspChain.setBass(eqBass);
			txDspChain.setMid(eqMid);
			txDspChain.setTreble(eqTreble);
		}
	});

	function onEqBass()   { txDspChain?.setBass(eqBass);     emit('eq_bass', eqBass); }
	function onEqMid()    { txDspChain?.setMid(eqMid);       emit('eq_mid', eqMid); }
	function onEqTreble() { txDspChain?.setTreble(eqTreble); emit('eq_treble', eqTreble); }

	// ── Compressor ────────────────────────────────────────────────────
	let compEnabled   = $state(false);
	let compPreset    = $state<CompressorPreset>('medium');
	let compThreshold = $state(-24);
	let compRatio     = $state(4);
	let compAttack    = $state(0.003);
	let compRelease   = $state(0.25);

	function onCompToggle(): void {
		txDspChain?.enableCompressor(compEnabled);
		if (compEnabled && compPreset !== 'manual') txDspChain?.setCompressorPreset(compPreset);
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
	let limEnabled   = $state(false);
	let limPreset    = $state<LimiterPreset>('medium');
	let limThreshold = $state(-3);
	let limRatio     = $state(10);
	let limAttack    = $state(0.002);
	let limRelease   = $state(0.05);

	function onLimEnabled(): void {
		txDspChain?.enableLimiter(limEnabled);
		if (limEnabled && limPreset !== 'manual') txDspChain?.setLimiterPreset(limPreset);
		emit('lim_enabled', limEnabled);
	}
	function onLimPreset(preset: LimiterPreset): void {
		limPreset = preset;
		if (limEnabled && preset !== 'manual') txDspChain?.setLimiterPreset(preset);
		emit('lim_preset', preset);
	}
	function onLimManual(): void {
		limPreset = 'manual';
		if (limEnabled) txDspChain?.setLimiter(limThreshold, limRatio, limAttack, limRelease);
		emit('lim_manual', { limThreshold, limRatio, limAttack, limRelease });
	}

	// ── Gate ──────────────────────────────────────────────────────────
	let gateThreshold = $state(-60);

	// Gate is always enabled; enable it whenever the chain becomes available
	$effect(() => {
		if (txDspChain) {
			txDspChain.enableGate(true);
			txDspChain.setGateThreshold(gateThreshold);
		}
	});

	function onGateThreshold(v: number): void {
		gateThreshold = v;
		txDspChain?.setGateThreshold(gateThreshold);
		emit('gate_threshold', gateThreshold);
	}

	// ── Mic mute ──────────────────────────────────────────────────────
	let micMuted = $state(false);

	function onMicMute(): void {
		micMuted = !micMuted;
		emit('mic_mute', micMuted);
	}

	const unavailable = $derived(!txDspChain);
</script>

<div class="tx-dsp" class:unavailable aria-label="TX DSP controls" role="group">

	<!-- ── EQ column ───────────────────────────────────────────────── -->
	<div class="dsp-col eq-col">
		<Knob value={eqBass}   min={-20} max={20} step={1} label="Bass"   size={52} defaultValue={0} onchange={(v) => { eqBass   = v; onEqBass();   }} />
		<Knob value={eqMid}    min={-20} max={20} step={1} label="Mid"    size={52} defaultValue={0} onchange={(v) => { eqMid    = v; onEqMid();    }} />
		<Knob value={eqTreble} min={-20} max={20} step={1} label="Treble" size={52} defaultValue={0} onchange={(v) => { eqTreble = v; onEqTreble(); }} />
	</div>

	<!-- ── Filters column ───────────────────────────────────────────── -->
	<div class="dsp-col filters-col">
		<button class="circle-btn" class:active={hpEnabled} disabled={unavailable}
			aria-pressed={hpEnabled} aria-label="Highpass filter" aria-haspopup="dialog"
			bind:this={hpEl} onclick={() => togglePopover('hp')}>HP</button>

		<button class="circle-btn" class:active={lpEnabled} disabled={unavailable}
			aria-pressed={lpEnabled} aria-label="Lowpass filter" aria-haspopup="dialog"
			bind:this={lpEl} onclick={() => togglePopover('lp')}>LP</button>

		<button class="circle-btn" class:active={compEnabled} disabled={unavailable}
			aria-pressed={compEnabled} aria-label="Compressor" aria-haspopup="dialog"
			bind:this={compEl} onclick={() => togglePopover('comp')}>Comp</button>

		<button class="circle-btn" class:active={limEnabled} disabled={unavailable}
			aria-pressed={limEnabled} aria-label="Limiter" aria-haspopup="dialog"
			bind:this={limEl} onclick={() => togglePopover('lim')}>Lim</button>
	</div>

	<!-- ── Gain / Gate column ───────────────────────────────────────── -->
	<div class="dsp-col right-col">
		<Knob value={txGain} min={0} max={100} step={5} label="Gain" size={52} defaultValue={50} onchange={onTxGainChange} />
		<Knob value={gateThreshold} min={-100} max={0} step={1} label="Gate" size={52} defaultValue={-60} onchange={onGateThreshold} />
		<button
			class="mic-lock"
			class:muted={micMuted}
			onclick={onMicMute}
			aria-pressed={micMuted}
			aria-label={micMuted ? 'Mic muted — click to unmute' : 'Mic active — click to mute'}
		>{micMuted ? 'MUTED' : 'MIC'}</button>
	</div>

</div>

<!-- ── Filter popovers ──────────────────────────────────────────── -->
{#if openFilter}
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<div
		class="popover"
		role="dialog"
		aria-modal="true"
		tabindex="-1"
		style={posStyle}
		bind:this={popoverEl}
		onkeydown={onPopoverKeydown}
	>
		{#if openFilter === 'hp'}
			<div class="pop-row toggle-row">
				<label class="toggle-label">
					<input type="checkbox" bind:checked={hpEnabled} onchange={onHpEnabled} />
					Enable
				</label>
			</div>
			<div class="pop-row slider-row" class:disabled={!hpEnabled}>
				<label for="tx-hp-freq">Freq</label>
				<input id="tx-hp-freq" type="range" min="50" max="500" step="10"
					bind:value={hpFreq} disabled={!hpEnabled} oninput={onHpFreq}
					aria-label="Highpass frequency" />
				<span class="val">{hpFreq} Hz</span>
			</div>

		{:else if openFilter === 'lp'}
			<div class="pop-row toggle-row">
				<label class="toggle-label">
					<input type="checkbox" bind:checked={lpEnabled} onchange={onLpEnabled} />
					Enable
				</label>
			</div>
			<div class="pop-row slider-row" class:disabled={!lpEnabled}>
				<label for="tx-lp-freq">Freq</label>
				<input id="tx-lp-freq" type="range" min="1500" max="5000" step="50"
					bind:value={lpFreq} disabled={!lpEnabled} oninput={onLpFreq}
					aria-label="Lowpass frequency" />
				<span class="val">{lpFreq} Hz</span>
			</div>

		{:else if openFilter === 'comp'}
			<div class="pop-row toggle-row">
				<label class="toggle-label">
					<input type="checkbox" bind:checked={compEnabled} onchange={onCompToggle} />
					Enable
				</label>
			</div>
			<div class="pop-row preset-row" class:disabled={!compEnabled}>
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
				<div class="pop-row slider-row" class:disabled={!compEnabled}>
					<label for="comp-thr">Thr</label>
					<input id="comp-thr" type="range" min="-60" max="0" step="1"
						bind:value={compThreshold} disabled={!compEnabled} oninput={onCompManual}
						aria-label="Compressor threshold" />
					<span class="val">{compThreshold} dB</span>
				</div>
				<div class="pop-row slider-row" class:disabled={!compEnabled}>
					<label for="comp-ratio">Ratio</label>
					<input id="comp-ratio" type="range" min="1" max="20" step="0.5"
						bind:value={compRatio} disabled={!compEnabled} oninput={onCompManual}
						aria-label="Compressor ratio" />
					<span class="val">{compRatio}:1</span>
				</div>
				<div class="pop-row slider-row" class:disabled={!compEnabled}>
					<label for="comp-atk">Atk</label>
					<input id="comp-atk" type="range" min="0.001" max="0.1" step="0.001"
						bind:value={compAttack} disabled={!compEnabled} oninput={onCompManual}
						aria-label="Compressor attack" />
					<span class="val">{(compAttack * 1000).toFixed(0)} ms</span>
				</div>
				<div class="pop-row slider-row" class:disabled={!compEnabled}>
					<label for="comp-rel">Rel</label>
					<input id="comp-rel" type="range" min="0.01" max="1" step="0.01"
						bind:value={compRelease} disabled={!compEnabled} oninput={onCompManual}
						aria-label="Compressor release" />
					<span class="val">{(compRelease * 1000).toFixed(0)} ms</span>
				</div>
			{/if}

		{:else if openFilter === 'lim'}
			<div class="pop-row toggle-row">
				<label class="toggle-label">
					<input type="checkbox" bind:checked={limEnabled} onchange={onLimEnabled} />
					Enable
				</label>
			</div>
			<div class="pop-row preset-row" class:disabled={!limEnabled}>
				{#each (['soft', 'medium', 'hard', 'manual'] as const) as preset}
					<button
						class="preset-pill"
						class:active={limPreset === preset}
						disabled={!limEnabled}
						onclick={() => onLimPreset(preset)}
						aria-pressed={limPreset === preset}
					>{preset}</button>
				{/each}
			</div>
			{#if limPreset === 'manual'}
				<div class="pop-row slider-row" class:disabled={!limEnabled}>
					<label for="lim-thr">Thr</label>
					<input id="lim-thr" type="range" min="-20" max="0" step="1"
						bind:value={limThreshold} disabled={!limEnabled} oninput={onLimManual}
						aria-label="Limiter threshold" />
					<span class="val">{limThreshold} dB</span>
				</div>
				<div class="pop-row slider-row" class:disabled={!limEnabled}>
					<label for="lim-ratio">Ratio</label>
					<input id="lim-ratio" type="range" min="1" max="20" step="0.5"
						bind:value={limRatio} disabled={!limEnabled} oninput={onLimManual}
						aria-label="Limiter ratio" />
					<span class="val">{limRatio}:1</span>
				</div>
				<div class="pop-row slider-row" class:disabled={!limEnabled}>
					<label for="lim-atk">Atk</label>
					<input id="lim-atk" type="range" min="0.001" max="0.1" step="0.001"
						bind:value={limAttack} disabled={!limEnabled} oninput={onLimManual}
						aria-label="Limiter attack" />
					<span class="val">{(limAttack * 1000).toFixed(0)} ms</span>
				</div>
				<div class="pop-row slider-row" class:disabled={!limEnabled}>
					<label for="lim-rel">Rel</label>
					<input id="lim-rel" type="range" min="0.01" max="1" step="0.01"
						bind:value={limRelease} disabled={!limEnabled} oninput={onLimManual}
						aria-label="Limiter release" />
					<span class="val">{(limRelease * 1000).toFixed(0)} ms</span>
				</div>
			{/if}
		{/if}
	</div>
{/if}

<style>
	.tx-dsp {
		display: flex;
		flex-direction: row;
		align-items: stretch;
		width: 100%;
	}

	.tx-dsp.unavailable {
		opacity: 0.4;
		pointer-events: none;
	}

	/* ── Shared column layout ── */
	.dsp-col {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 6px;
		padding: 8px 10px;
	}

	.eq-col,
	.filters-col {
		border-right: 1px solid var(--er-divider);
	}

	.right-col {
		flex: 1;
		align-items: center;
	}

	/* ── Circle filter buttons (filters column) ── */
	.circle-btn {
		width: 48px;
		height: 48px;
		border-radius: 50%;
		border: 1px solid var(--er-ctrl-border);
		background: var(--er-ctrl-bg);
		color: var(--er-ctrl-text);
		font-size: 0.65rem;
		font-weight: 700;
		letter-spacing: 0.04em;
		cursor: pointer;
		white-space: nowrap;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		transition: background 0.1s, border-color 0.1s, color 0.1s;
	}

	.circle-btn:hover:not(:disabled):not(.active) {
		border-color: var(--er-ctrl-hover-border);
		background: var(--er-ctrl-hover-bg);
		color: var(--er-ctrl-hover-text);
	}

	.circle-btn.active {
		background: var(--er-accent-bg);
		border-color: var(--er-accent);
		color: var(--er-accent-text);
	}

	.circle-btn:disabled { opacity: var(--er-ctrl-disabled); cursor: not-allowed; }
	.circle-btn:focus-visible { outline: 2px solid var(--er-accent); outline-offset: 2px; }

	/* ── Mic mute button — fixed size to prevent layout shift ── */
	.mic-lock {
		width: 48px;
		height: 48px;
		padding: 0;
		border-radius: 50%;
		border: 1px solid var(--er-ctrl-border);
		background: var(--er-ctrl-bg);
		color: var(--er-ctrl-text);
		font-size: 0.62rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		transition: background 0.1s, border-color 0.1s, color 0.1s;
	}

	.mic-lock:hover:not(.muted) {
		border-color: var(--er-ctrl-hover-border);
		color: var(--er-ctrl-hover-text);
	}

	.mic-lock.muted {
		background: var(--er-red-active);
		border-color: var(--er-red);
		color: var(--er-accent-text);
	}

	.mic-lock:focus-visible {
		outline: 2px solid var(--er-accent);
		outline-offset: 2px;
	}

	.val {
		font-size: 0.68rem;
		font-family: var(--er-label-font);
		color: var(--er-ctrl-hover-text);
		white-space: nowrap;
		min-width: 52px;
		text-align: right;
	}


	.preset-row {
		display: flex;
		gap: 4px;
		flex-wrap: wrap;
	}

	.preset-pill {
		padding: 2px 8px;
		border-radius: 4px;
		border: 1px solid var(--er-ctrl-border);
		background: var(--er-ctrl-bg);
		color: var(--er-ctrl-text);
		font-size: 0.68rem;
		font-weight: 600;
		cursor: pointer;
		transition: background 0.1s, border-color 0.1s, color 0.1s;
	}

	.preset-pill:hover:not(:disabled):not(.active) { border-color: var(--er-ctrl-hover-border); color: var(--er-ctrl-hover-text); }
	.preset-pill.active { background: var(--er-accent-bg); border-color: var(--er-accent); color: var(--er-accent-text); }
	.preset-pill:disabled { opacity: var(--er-ctrl-disabled); cursor: not-allowed; }
	.preset-pill:focus-visible { outline: 2px solid var(--er-accent); outline-offset: 2px; }

	.slider-row {
		display: grid;
		grid-template-columns: 36px 1fr 52px;
		align-items: center;
		gap: 5px;
	}

	.slider-row.disabled {
		opacity: var(--er-ctrl-disabled);
		pointer-events: none;
	}

	.slider-row label {
		font-size: 0.72rem;
		color: var(--er-ctrl-text);
		white-space: nowrap;
	}

	.slider-row input[type='range'] {
		width: 100%;
		accent-color: var(--er-accent);
	}

	/* ── Popover preset row ── */
	.pop-row.preset-row {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
	}

	.pop-row.preset-row.disabled {
		opacity: var(--er-ctrl-disabled);
		pointer-events: none;
	}

	/* ── Popover ── */
	.popover {
		min-width: 220px;
		background: var(--er-panel-dark);
		border: 1px solid var(--er-ctrl-border);
		border-radius: 6px;
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
		padding: 8px 10px;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.pop-row {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.toggle-row {
		padding-bottom: 2px;
		border-bottom: 1px solid var(--er-divider);
	}

	.toggle-label {
		display: flex;
		align-items: center;
		gap: 5px;
		font-size: 0.78rem;
		color: var(--er-ctrl-hover-text);
		cursor: pointer;
	}

	@media (prefers-reduced-motion: reduce) {
		.preset-pill { transition: none; }
	}
</style>
