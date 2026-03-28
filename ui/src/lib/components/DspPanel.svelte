<script lang="ts">
	import type { DspChain } from '$lib/audio/dsp-chain.js';
	import { scrollWheel } from '$lib/actions/scrollwheel.js';

	interface Props {
		dspChain: DspChain | null;
	}
	let { dspChain }: Props = $props();

	// Section open/closed state
	let filtersOpen = $state(true);
	let nrOpen = $state(false);
	let eqOpen = $state(false);
	let compressorOpen = $state(false);

	// Filter params
	let filtersEnabled = $state(false);
	let bpCenter = $state(1500);
	let bpWidth = $state(2400);
	let notchEnabled = $state(false);
	let notchCenter = $state(1000);
	let notchWidth = $state(50);

	// Noise reduction
	let nrEnabled = $state(false);
	let nrAmount = $state(0.5);

	// EQ
	let eqEnabled = $state(false);
	let bassGain = $state(0);
	let midGain = $state(0);
	let trebleGain = $state(0);

	// Compressor
	let compressorEnabled = $state(false);
	let compThreshold = $state(-24);
	let compRatio = $state(4);

	// --- Apply changes immediately when params change ---

	$effect(() => {
		if (!dspChain) return;
		dspChain.enableBandpass(filtersEnabled);
		if (filtersEnabled) {
			dspChain.setBandpass(bpCenter, bpWidth);
		}
	});

	$effect(() => {
		if (!dspChain) return;
		dspChain.enableNotch(notchEnabled);
		if (notchEnabled) {
			dspChain.setNotch(notchCenter, notchWidth);
		}
	});

	$effect(() => {
		if (!dspChain) return;
		dspChain.enableNr(nrEnabled);
		if (nrEnabled) {
			dspChain.setNrAmount(nrAmount);
		}
	});

	$effect(() => {
		if (!dspChain) return;
		dspChain.enableEq(eqEnabled);
		if (eqEnabled) {
			dspChain.setBass(bassGain);
			dspChain.setMid(midGain);
			dspChain.setTreble(trebleGain);
		}
	});

	$effect(() => {
		if (!dspChain) return;
		dspChain.enableCompressor(compressorEnabled);
		if (compressorEnabled) {
			dspChain.setCompressor(compThreshold, compRatio, 0.003, 0.25);
		}
	});

	function nudge(val: number, min: number, max: number, step: number, delta: number): number {
		return Math.max(min, Math.min(max, val + delta * step));
	}
</script>

<div class="dsp-panel" aria-label="DSP controls">

	<!-- ── Filters ─────────────────────────────────────────── -->
	<details bind:open={filtersOpen}>
		<summary class="section-header">
			<span>Filters</span>
			<label class="toggle" onclick={(e) => e.stopPropagation()}>
				<input
					type="checkbox"
					bind:checked={filtersEnabled}
					aria-label="Enable filters"
				/>
				<span class="toggle-label">{filtersEnabled ? 'On' : 'Off'}</span>
			</label>
		</summary>

		<div class="section-body" class:disabled={!filtersEnabled}>
			<fieldset>
				<legend>Bandpass</legend>

				<div class="row" use:scrollWheel={{ onDelta: (d) => { bpCenter = nudge(bpCenter, 100, 8000, 50, d); } }}>
					<label for="bp-center">Center (Hz)</label>
					<input
						id="bp-center"
						type="range"
						min="100"
						max="8000"
						step="50"
						bind:value={bpCenter}
						disabled={!filtersEnabled}
						aria-label="Bandpass center frequency in Hz"
					/>
					<span class="val">{bpCenter}</span>
				</div>

				<div class="row" use:scrollWheel={{ onDelta: (d) => { bpWidth = nudge(bpWidth, 50, 6000, 50, d); } }}>
					<label for="bp-width">Width (Hz)</label>
					<input
						id="bp-width"
						type="range"
						min="50"
						max="6000"
						step="50"
						bind:value={bpWidth}
						disabled={!filtersEnabled}
						aria-label="Bandpass width in Hz"
					/>
					<span class="val">{bpWidth}</span>
				</div>
			</fieldset>

			<fieldset>
				<legend>
					Notch
					<label class="toggle inline">
						<input
							type="checkbox"
							bind:checked={notchEnabled}
							disabled={!filtersEnabled}
							aria-label="Enable notch filter"
						/>
						<span class="toggle-label">{notchEnabled ? 'On' : 'Off'}</span>
					</label>
				</legend>

				<div class="row" use:scrollWheel={{ onDelta: (d) => { notchCenter = nudge(notchCenter, 100, 8000, 50, d); } }}>
					<label for="notch-center">Center (Hz)</label>
					<input
						id="notch-center"
						type="range"
						min="100"
						max="8000"
						step="50"
						bind:value={notchCenter}
						disabled={!filtersEnabled || !notchEnabled}
						aria-label="Notch center frequency in Hz"
					/>
					<span class="val">{notchCenter}</span>
				</div>

				<div class="row" use:scrollWheel={{ onDelta: (d) => { notchWidth = nudge(notchWidth, 10, 500, 10, d); } }}>
					<label for="notch-width">Width (Hz)</label>
					<input
						id="notch-width"
						type="range"
						min="10"
						max="500"
						step="10"
						bind:value={notchWidth}
						disabled={!filtersEnabled || !notchEnabled}
						aria-label="Notch width in Hz"
					/>
					<span class="val">{notchWidth}</span>
				</div>
			</fieldset>
		</div>
	</details>

	<!-- ── Noise Reduction ─────────────────────────────────── -->
	<details bind:open={nrOpen}>
		<summary class="section-header">
			<span>Noise Reduction</span>
			<label class="toggle" onclick={(e) => e.stopPropagation()}>
				<input
					type="checkbox"
					bind:checked={nrEnabled}
					disabled={!dspChain?.isNrAvailable()}
					aria-label="Enable noise reduction"
				/>
				<span class="toggle-label">
					{#if !dspChain?.isNrAvailable()}Unavailable{:else if nrEnabled}On{:else}Off{/if}
				</span>
			</label>
		</summary>

		<div class="section-body" class:disabled={!nrEnabled}>
			<div class="row" use:scrollWheel={{ onDelta: (d) => { nrAmount = nudge(nrAmount, 0, 1, 0.05, d); } }}>
				<label for="nr-amount">Amount</label>
				<input
					id="nr-amount"
					type="range"
					min="0"
					max="1"
					step="0.05"
					bind:value={nrAmount}
					disabled={!nrEnabled}
					aria-label="Noise reduction amount (0 to 1)"
				/>
				<span class="val">{nrAmount.toFixed(2)}</span>
			</div>
		</div>
	</details>

	<!-- ── EQ ──────────────────────────────────────────────── -->
	<details bind:open={eqOpen}>
		<summary class="section-header">
			<span>EQ</span>
			<label class="toggle" onclick={(e) => e.stopPropagation()}>
				<input
					type="checkbox"
					bind:checked={eqEnabled}
					aria-label="Enable equalizer"
				/>
				<span class="toggle-label">{eqEnabled ? 'On' : 'Off'}</span>
			</label>
		</summary>

		<div class="section-body" class:disabled={!eqEnabled}>
			<div class="row" use:scrollWheel={{ onDelta: (d) => { bassGain = nudge(bassGain, -12, 12, 1, d); } }}>
				<label for="eq-bass">Bass (dB)</label>
				<input
					id="eq-bass"
					type="range"
					min="-12"
					max="12"
					step="1"
					bind:value={bassGain}
					disabled={!eqEnabled}
					aria-label="Bass gain in dB"
				/>
				<span class="val">{bassGain > 0 ? '+' : ''}{bassGain}</span>
			</div>

			<div class="row" use:scrollWheel={{ onDelta: (d) => { midGain = nudge(midGain, -12, 12, 1, d); } }}>
				<label for="eq-mid">Mid (dB)</label>
				<input
					id="eq-mid"
					type="range"
					min="-12"
					max="12"
					step="1"
					bind:value={midGain}
					disabled={!eqEnabled}
					aria-label="Mid gain in dB"
				/>
				<span class="val">{midGain > 0 ? '+' : ''}{midGain}</span>
			</div>

			<div class="row" use:scrollWheel={{ onDelta: (d) => { trebleGain = nudge(trebleGain, -12, 12, 1, d); } }}>
				<label for="eq-treble">Treble (dB)</label>
				<input
					id="eq-treble"
					type="range"
					min="-12"
					max="12"
					step="1"
					bind:value={trebleGain}
					disabled={!eqEnabled}
					aria-label="Treble gain in dB"
				/>
				<span class="val">{trebleGain > 0 ? '+' : ''}{trebleGain}</span>
			</div>
		</div>
	</details>

	<!-- ── Compressor ──────────────────────────────────────── -->
	<details bind:open={compressorOpen}>
		<summary class="section-header">
			<span>Compressor</span>
			<label class="toggle" onclick={(e) => e.stopPropagation()}>
				<input
					type="checkbox"
					bind:checked={compressorEnabled}
					aria-label="Enable compressor"
				/>
				<span class="toggle-label">{compressorEnabled ? 'On' : 'Off'}</span>
			</label>
		</summary>

		<div class="section-body" class:disabled={!compressorEnabled}>
			<div class="row" use:scrollWheel={{ onDelta: (d) => { compThreshold = nudge(compThreshold, -60, 0, 1, d); } }}>
				<label for="comp-threshold">Threshold (dB)</label>
				<input
					id="comp-threshold"
					type="range"
					min="-60"
					max="0"
					step="1"
					bind:value={compThreshold}
					disabled={!compressorEnabled}
					aria-label="Compressor threshold in dBFS"
				/>
				<span class="val">{compThreshold}</span>
			</div>

			<div class="row" use:scrollWheel={{ onDelta: (d) => { compRatio = nudge(compRatio, 1, 20, 1, d); } }}>
				<label for="comp-ratio">Ratio</label>
				<input
					id="comp-ratio"
					type="range"
					min="1"
					max="20"
					step="1"
					bind:value={compRatio}
					disabled={!compressorEnabled}
					aria-label="Compressor ratio"
				/>
				<span class="val">{compRatio}:1</span>
			</div>
		</div>
	</details>

</div>

<style>
	.dsp-panel {
		display: flex;
		flex-direction: column;
		gap: 2px;
		font-size: 0.82rem;
		color: #ccc;
	}

	details {
		border: 1px solid #2a2a2a;
		border-radius: 4px;
		overflow: hidden;
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
		font-weight: 600;
		font-size: 0.8rem;
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

	fieldset {
		border: 1px solid #2a2a2a;
		border-radius: 3px;
		margin: 0;
		padding: 6px 8px;
	}

	legend {
		font-size: 0.75rem;
		color: #888;
		padding: 0 4px;
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.row {
		display: grid;
		grid-template-columns: 90px 1fr 44px;
		align-items: center;
		gap: 6px;
	}

	label {
		font-size: 0.75rem;
		color: #999;
		white-space: nowrap;
	}

	input[type='range'] {
		width: 100%;
		accent-color: #4a9eff;
	}

	.val {
		font-size: 0.72rem;
		font-family: 'Courier New', monospace;
		color: #aaa;
		text-align: right;
		white-space: nowrap;
	}

	.toggle {
		display: flex;
		align-items: center;
		gap: 4px;
		cursor: pointer;
		font-size: 0.72rem;
		font-weight: 400;
		color: #888;
	}

	.toggle.inline {
		display: inline-flex;
	}

	.toggle-label {
		min-width: 34px;
	}
</style>
