<script lang="ts">
	import type { RxDspChain } from '$lib/audio/rx-dsp-chain.js';
	import { onDestroy } from 'svelte';

	type FilterKey =
		| 'highpass'
		| 'lowpass'
		| 'peak'
		| 'noiseBlanker'
		| 'notch'
		| 'bandpass'
		| 'nr';

	interface Props {
		rxDspChain: RxDspChain | null;
		filter: FilterKey;
		open: boolean;
		anchor: HTMLElement | null;
		onchange?: (detail: Record<string, unknown>) => void;
	}

	let { rxDspChain, filter, open = $bindable(false), anchor, onchange }: Props = $props();

	// ── Per-filter local state ────────────────────────────────────────

	// Shared
	let enabled = $state(false);

	// Highpass
	let hpFreq = $state(200);

	// Lowpass
	let lpFreq = $state(2800);

	// Peak
	let peakFreq = $state(1000);
	let peakGain = $state(0);
	let peakQ = $state(1.0);

	// Noise blanker
	let nbFreq = $state<50 | 60>(50);

	// Notch
	let notchMode = $state<'manual' | 'auto'>('manual');
	let notchFreq = $state(1000);
	let notchQ = $state(10);

	// Bandpass
	let bpPreset = $state<'voice' | 'cw' | 'manual'>('voice');
	let bpCenter = $state(1500);
	let bpWidth = $state(2400);

	// NR
	let nrAmount = $state(0.5);

	// ── Positioning ───────────────────────────────────────────────────

	let popoverEl: HTMLDivElement | undefined;

	let posStyle = $derived.by(() => {
		if (!anchor || !open) return '';
		const rect = anchor.getBoundingClientRect();
		return `position:fixed; top:${rect.bottom + 4}px; left:${rect.left}px; z-index:200;`;
	});

	// ── Focus trap ────────────────────────────────────────────────────

	function trapFocus(e: KeyboardEvent): void {
		if (!popoverEl) return;
		const focusable = Array.from(
			popoverEl.querySelectorAll<HTMLElement>(
				'button, input, [tabindex]:not([tabindex="-1"])',
			),
		).filter((el) => !el.hasAttribute('disabled'));
		if (focusable.length === 0) return;
		const first = focusable[0];
		const last = focusable[focusable.length - 1];
		if (e.key === 'Tab') {
			if (e.shiftKey) {
				if (document.activeElement === first) {
					e.preventDefault();
					last.focus();
				}
			} else {
				if (document.activeElement === last) {
					e.preventDefault();
					first.focus();
				}
			}
		}
	}

	function onKeydown(e: KeyboardEvent): void {
		if (e.key === 'Escape') {
			open = false;
		} else {
			trapFocus(e);
		}
	}

	// ── Click-outside ─────────────────────────────────────────────────

	function onClickOutside(e: MouseEvent): void {
		if (!open) return;
		const target = e.target as Node;
		if (popoverEl && !popoverEl.contains(target) && anchor && !anchor.contains(target)) {
			open = false;
		}
	}

	$effect(() => {
		if (open) {
			document.addEventListener('click', onClickOutside, true);
			// Move focus into popover on open
			requestAnimationFrame(() => {
				if (popoverEl) {
					const first = popoverEl.querySelector<HTMLElement>(
						'button, input, [tabindex]:not([tabindex="-1"])',
					);
					first?.focus();
				}
			});
		} else {
			document.removeEventListener('click', onClickOutside, true);
		}
		return () => document.removeEventListener('click', onClickOutside, true);
	});

	onDestroy(() => {
		document.removeEventListener('click', onClickOutside, true);
	});

	// ── Helpers ───────────────────────────────────────────────────────

	function emitChange(extra: Record<string, unknown> = {}): void {
		onchange?.({ filter, enabled, ...extra });
	}

	// ── Highpass handlers ─────────────────────────────────────────────

	function onHpEnabled(): void {
		rxDspChain?.enableHighpass(enabled);
		if (enabled) rxDspChain?.setHighpass(hpFreq);
		emitChange({ hpFreq });
	}

	function onHpFreq(): void {
		if (enabled) rxDspChain?.setHighpass(hpFreq);
		emitChange({ hpFreq });
	}

	// ── Lowpass handlers ──────────────────────────────────────────────

	function onLpEnabled(): void {
		rxDspChain?.enableLowpass(enabled);
		if (enabled) rxDspChain?.setLowpass(lpFreq);
		emitChange({ lpFreq });
	}

	function onLpFreq(): void {
		if (enabled) rxDspChain?.setLowpass(lpFreq);
		emitChange({ lpFreq });
	}

	// ── Peak handlers ─────────────────────────────────────────────────

	function onPeakEnabled(): void {
		rxDspChain?.enablePeak(enabled);
		if (enabled) rxDspChain?.setPeak(peakFreq, peakGain, peakQ);
		emitChange({ peakFreq, peakGain, peakQ });
	}

	function onPeakParam(): void {
		if (enabled) rxDspChain?.setPeak(peakFreq, peakGain, peakQ);
		emitChange({ peakFreq, peakGain, peakQ });
	}

	// ── Noise blanker handlers ────────────────────────────────────────

	function onNbEnabled(): void {
		rxDspChain?.enableNoiseBlanker(enabled);
		if (enabled) rxDspChain?.setNoiseBlankerFreq(nbFreq);
		emitChange({ nbFreq });
	}

	function onNbFreq(): void {
		if (enabled) rxDspChain?.setNoiseBlankerFreq(nbFreq);
		emitChange({ nbFreq });
	}

	// ── Notch handlers ────────────────────────────────────────────────

	function onNotchEnabled(): void {
		rxDspChain?.enableNotch(enabled);
		if (enabled) {
			rxDspChain?.setNotchMode(notchMode);
			if (notchMode === 'manual') rxDspChain?.setNotch(notchFreq, notchQ);
		}
		emitChange({ notchMode, notchFreq, notchQ });
	}

	function onNotchMode(): void {
		rxDspChain?.setNotchMode(notchMode);
		if (enabled && notchMode === 'manual') rxDspChain?.setNotch(notchFreq, notchQ);
		emitChange({ notchMode, notchFreq, notchQ });
	}

	function onNotchParam(): void {
		if (enabled && notchMode === 'manual') rxDspChain?.setNotch(notchFreq, notchQ);
		emitChange({ notchMode, notchFreq, notchQ });
	}

	// ── Bandpass handlers ─────────────────────────────────────────────

	function onBpEnabled(): void {
		rxDspChain?.enableBandpass(enabled);
		if (enabled) {
			rxDspChain?.setBandpassPreset(bpPreset);
			if (bpPreset === 'manual') rxDspChain?.setBandpass(bpCenter, bpWidth);
		}
		emitChange({ bpPreset, bpCenter, bpWidth });
	}

	function onBpPreset(preset: 'voice' | 'cw' | 'manual'): void {
		bpPreset = preset;
		rxDspChain?.setBandpassPreset(preset);
		if (preset === 'manual') rxDspChain?.setBandpass(bpCenter, bpWidth);
		emitChange({ bpPreset, bpCenter, bpWidth });
	}

	function onBpParam(): void {
		if (bpPreset === 'manual') rxDspChain?.setBandpass(bpCenter, bpWidth);
		emitChange({ bpPreset, bpCenter, bpWidth });
	}

	// ── NR handlers ───────────────────────────────────────────────────

	function onNrEnabled(): void {
		rxDspChain?.enableNr(enabled);
		if (enabled) rxDspChain?.setNrAmount(nrAmount);
		emitChange({ nrAmount });
	}

	function onNrAmount(): void {
		if (enabled) rxDspChain?.setNrAmount(nrAmount);
		emitChange({ nrAmount });
	}
</script>

{#if open}
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<div
		class="popover"
		role="dialog"
		aria-label="{filter} filter settings"
		style={posStyle}
		bind:this={popoverEl}
		onkeydown={onKeydown}
	>

		{#if filter === 'highpass'}
			<!-- ── Highpass ─────────────────────────────── -->
			<div class="row toggle-row">
				<label class="toggle-label">
					<input type="checkbox" bind:checked={enabled} onchange={onHpEnabled} />
					Enable
				</label>
			</div>
			<div class="row slider-row" class:disabled={!enabled}>
				<label for="hp-freq">Freq</label>
				<input
					id="hp-freq"
					type="range"
					min="50"
					max="500"
					step="10"
					bind:value={hpFreq}
					disabled={!enabled}
					oninput={onHpFreq}
					aria-label="Highpass cutoff frequency in Hz"
				/>
				<span class="val">{hpFreq} Hz</span>
			</div>

		{:else if filter === 'lowpass'}
			<!-- ── Lowpass ──────────────────────────────── -->
			<div class="row toggle-row">
				<label class="toggle-label">
					<input type="checkbox" bind:checked={enabled} onchange={onLpEnabled} />
					Enable
				</label>
			</div>
			<div class="row slider-row" class:disabled={!enabled}>
				<label for="lp-freq">Freq</label>
				<input
					id="lp-freq"
					type="range"
					min="1500"
					max="5000"
					step="50"
					bind:value={lpFreq}
					disabled={!enabled}
					oninput={onLpFreq}
					aria-label="Lowpass cutoff frequency in Hz"
				/>
				<span class="val">{lpFreq} Hz</span>
			</div>

		{:else if filter === 'peak'}
			<!-- ── Peak ─────────────────────────────────── -->
			<div class="row toggle-row">
				<label class="toggle-label">
					<input type="checkbox" bind:checked={enabled} onchange={onPeakEnabled} />
					Enable
				</label>
			</div>
			<div class="row slider-row" class:disabled={!enabled}>
				<label for="peak-freq">Freq</label>
				<input
					id="peak-freq"
					type="range"
					min="200"
					max="4000"
					step="50"
					bind:value={peakFreq}
					disabled={!enabled}
					oninput={onPeakParam}
					aria-label="Peak filter frequency in Hz"
				/>
				<span class="val">{peakFreq} Hz</span>
			</div>
			<div class="row slider-row" class:disabled={!enabled}>
				<label for="peak-gain">Gain</label>
				<input
					id="peak-gain"
					type="range"
					min="-20"
					max="20"
					step="1"
					bind:value={peakGain}
					disabled={!enabled}
					oninput={onPeakParam}
					aria-label="Peak filter gain in dB"
				/>
				<span class="val">{peakGain > 0 ? '+' : ''}{peakGain} dB</span>
			</div>
			<div class="row slider-row" class:disabled={!enabled}>
				<label for="peak-q">Q</label>
				<input
					id="peak-q"
					type="range"
					min="0.1"
					max="30"
					step="0.1"
					bind:value={peakQ}
					disabled={!enabled}
					oninput={onPeakParam}
					aria-label="Peak filter Q factor"
				/>
				<span class="val">{peakQ.toFixed(1)}</span>
			</div>

		{:else if filter === 'noiseBlanker'}
			<!-- ── Noise blanker ─────────────────────────── -->
			<div class="row toggle-row">
				<label class="toggle-label">
					<input type="checkbox" bind:checked={enabled} onchange={onNbEnabled} />
					Enable
				</label>
			</div>
			<div class="row radio-row" class:disabled={!enabled}>
				<span class="radio-label">Mains</span>
				<label class="radio-option">
					<input
						type="radio"
						name="nb-freq"
						value={50}
						bind:group={nbFreq}
						disabled={!enabled}
						onchange={onNbFreq}
						aria-label="50 Hz mains frequency"
					/>
					50 Hz
				</label>
				<label class="radio-option">
					<input
						type="radio"
						name="nb-freq"
						value={60}
						bind:group={nbFreq}
						disabled={!enabled}
						onchange={onNbFreq}
						aria-label="60 Hz mains frequency"
					/>
					60 Hz
				</label>
			</div>

		{:else if filter === 'notch'}
			<!-- ── Notch ─────────────────────────────────── -->
			<div class="row toggle-row">
				<label class="toggle-label">
					<input type="checkbox" bind:checked={enabled} onchange={onNotchEnabled} />
					Enable
				</label>
			</div>
			<div class="row radio-row" class:disabled={!enabled}>
				<span class="radio-label">Mode</span>
				<label class="radio-option">
					<input
						type="radio"
						name="notch-mode"
						value="manual"
						bind:group={notchMode}
						disabled={!enabled}
						onchange={onNotchMode}
						aria-label="Manual notch mode"
					/>
					Manual
				</label>
				<label class="radio-option">
					<input
						type="radio"
						name="notch-mode"
						value="auto"
						bind:group={notchMode}
						disabled={!enabled}
						onchange={onNotchMode}
						aria-label="Auto notch mode"
					/>
					Auto
				</label>
			</div>
			{#if notchMode === 'manual'}
				<div class="row slider-row" class:disabled={!enabled}>
					<label for="notch-freq">Freq</label>
					<input
						id="notch-freq"
						type="range"
						min="100"
						max="5000"
						step="50"
						bind:value={notchFreq}
						disabled={!enabled}
						oninput={onNotchParam}
						aria-label="Notch center frequency in Hz"
					/>
					<span class="val">{notchFreq} Hz</span>
				</div>
				<div class="row slider-row" class:disabled={!enabled}>
					<label for="notch-q">Q</label>
					<input
						id="notch-q"
						type="range"
						min="1"
						max="50"
						step="0.5"
						bind:value={notchQ}
						disabled={!enabled}
						oninput={onNotchParam}
						aria-label="Notch filter Q factor"
					/>
					<span class="val">{notchQ.toFixed(1)}</span>
				</div>
			{/if}

		{:else if filter === 'bandpass'}
			<!-- ── Bandpass ──────────────────────────────── -->
			<div class="row toggle-row">
				<label class="toggle-label">
					<input type="checkbox" bind:checked={enabled} onchange={onBpEnabled} />
					Enable
				</label>
			</div>
			<div class="row preset-row">
				{#each (['voice', 'cw', 'manual'] as const) as preset}
					<button
						class="preset-pill"
						class:active={bpPreset === preset}
						disabled={!enabled}
						onclick={() => onBpPreset(preset)}
						aria-pressed={bpPreset === preset}
					>{preset === 'voice' ? 'Voice' : preset === 'cw' ? 'CW' : 'Manual'}</button>
				{/each}
			</div>
			{#if bpPreset === 'manual'}
				<div class="row slider-row" class:disabled={!enabled}>
					<label for="bp-center">Center</label>
					<input
						id="bp-center"
						type="range"
						min="200"
						max="4000"
						step="50"
						bind:value={bpCenter}
						disabled={!enabled}
						oninput={onBpParam}
						aria-label="Bandpass center frequency in Hz"
					/>
					<span class="val">{bpCenter} Hz</span>
				</div>
				<div class="row slider-row" class:disabled={!enabled}>
					<label for="bp-width">Width</label>
					<input
						id="bp-width"
						type="range"
						min="100"
						max="5000"
						step="50"
						bind:value={bpWidth}
						disabled={!enabled}
						oninput={onBpParam}
						aria-label="Bandpass filter width in Hz"
					/>
					<span class="val">{bpWidth} Hz</span>
				</div>
			{/if}

		{:else if filter === 'nr'}
			<!-- ── NR ───────────────────────────────────── -->
			<div class="row toggle-row">
				<label class="toggle-label">
					<input type="checkbox" bind:checked={enabled} onchange={onNrEnabled} />
					Enable
				</label>
			</div>
			<div class="row slider-row" class:disabled={!enabled}>
				<label for="nr-amount">Amount</label>
				<input
					id="nr-amount"
					type="range"
					min="0"
					max="1"
					step="0.01"
					bind:value={nrAmount}
					disabled={!enabled}
					oninput={onNrAmount}
					aria-label="Noise reduction amount from 0 to 100 percent"
				/>
				<span class="val">{Math.round(nrAmount * 100)}%</span>
			</div>
		{/if}

	</div>
{/if}

<style>
	.popover {
		min-width: 220px;
		background: #141414;
		border: 1px solid #333;
		border-radius: 6px;
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
		padding: 8px 10px;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.row {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.toggle-row {
		padding-bottom: 2px;
		border-bottom: 1px solid #222;
	}

	.toggle-label {
		display: flex;
		align-items: center;
		gap: 5px;
		font-size: 0.78rem;
		color: #bbb;
		cursor: pointer;
	}

	.slider-row {
		display: grid;
		grid-template-columns: 52px 1fr 60px;
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

	.radio-row {
		gap: 8px;
		font-size: 0.78rem;
		color: #bbb;
	}

	.radio-row.disabled {
		opacity: 0.4;
		pointer-events: none;
	}

	.radio-label {
		font-size: 0.72rem;
		color: #999;
		white-space: nowrap;
	}

	.radio-option {
		display: flex;
		align-items: center;
		gap: 3px;
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
