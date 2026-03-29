<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { getStatus, getConfig, getRadioCat, getPresets, postAudioVolume, getDspConfig, patchDspConfig } from '$lib/api.js';
	import type { RxDspConfig, TxDspConfig } from '$lib/api.js';
	import { radioState, appConfig } from '$lib/stores.js';
	import { ControlWebSocket, AudioWebSocket } from '$lib/websocket.js';
	import { AudioManager } from '$lib/audio/audio-manager.js';
	import { activeLayout } from '$lib/layout/store.js';
	import type { LayoutConfig, LayoutPanel } from '$lib/layout/types.js';
	import VisualizationPanel from '$lib/components/VisualizationPanel.svelte';
	import FrequencyDisplay from '$lib/components/FrequencyDisplay.svelte';
	import BandSelector from '$lib/components/BandSelector.svelte';
	import ModeSelector from '$lib/components/ModeSelector.svelte';
	import PttButton from '$lib/components/PttButton.svelte';
	import SmeterDisplay from '$lib/components/SmeterDisplay.svelte';
	import AudioControls from '$lib/components/AudioControls.svelte';
	import LufsMeter from '$lib/components/LufsMeter.svelte';
	import DspPanel from '$lib/components/DspPanel.svelte';
	import RxDspPillRow from '$lib/components/RxDspPillRow.svelte';
	import TxDspPanel from '$lib/components/TxDspPanel.svelte';
	import PresetSelector from '$lib/components/PresetSelector.svelte';
	import VfoSelector from '$lib/components/VfoSelector.svelte';
	import CatExtended from '$lib/components/CatExtended.svelte';
	import TuningKnob from '$lib/components/TuningKnob.svelte';
	import Knob from '$lib/components/Knob.svelte';
	import LayoutManager from '$lib/components/LayoutManager.svelte';
	import type { VisualizationMode } from '$lib/viz/types.js';
	import type { RadioState, PresetConfig } from '$lib/types.js';
	import type { DspChain } from '$lib/audio/dsp-chain.js';
	import type { RxDspChain } from '$lib/audio/rx-dsp-chain.js';
	import type { TxDspChain } from '$lib/audio/tx-dsp-chain.js';

	let radioId: string | null = $state(null);
	let radio: RadioState = $state({
		id: '',
		name: '',
		freq: 14.2,
		mode: 'USB',
		ptt: false,
		online: false,
		simulation: false,
		smeter: 0,
		vfo: 'VFOA',
		swr: 1.0,
		ctcss_tone: 0,
	});
	let rxVolume = $state(50);
	let txGain = $state(50);

	let txGainTimer: ReturnType<typeof setTimeout> | null = null;
	function onTxGainChange(v: number) {
		txGain = v;
		if (txGainTimer) clearTimeout(txGainTimer);
		txGainTimer = setTimeout(() => {
			postAudioVolume(radioId ?? '', rxVolume, txGain, 0).catch((e) => {
				console.error('Failed to save tx gain:', e);
			});
		}, 300);
	}

	function handleRxDspChange(detail: Record<string, unknown>): void {
		if (!radioId) return;
		// Build a partial RxDspConfig patch from the changed fields
		const patch: Partial<RxDspConfig> = detail as Partial<RxDspConfig>;
		patchDspConfig(radioId, { rx: patch }).catch((e) => {
			console.warn('[DSP] Failed to persist RX DSP change:', e);
		});
	}

	function handleTxDspChange(detail: { param: string; value: unknown }): void {
		if (!radioId) return;
		const patch: Partial<TxDspConfig> = { [detail.param]: detail.value } as Partial<TxDspConfig>;
		patchDspConfig(radioId, { tx: patch }).catch((e) => {
			console.warn('[DSP] Failed to persist TX DSP change:', e);
		});
	}

	let controlWs: ControlWebSocket | null = $state(null);
	let audioWs: AudioWebSocket | null = null;
	let audioMgr: AudioManager | null = $state(null);
	let dspChain: DspChain | null = $state(null);
	let rxDspChain: RxDspChain | null = $state(null);
	let txDspChain: TxDspChain | null = $state(null);

	// Presets
	let presets: PresetConfig[] = $state([]);

	// Region and enabled bands from config
	let region = $state('us');
	let enabledBands: string[] = $state([]);

	// Visualization mode — persisted in localStorage
	const VIZ_MODES: VisualizationMode[] = ['waterfall', 'spectrum', 'oscilloscope', 'constellation', 'phase', 'spectrogram3d'];
	const VIZ_STORAGE_KEY = 'riglet:vizMode';
	function loadVizMode(): VisualizationMode {
		try {
			const stored = localStorage.getItem(VIZ_STORAGE_KEY) as VisualizationMode;
			if (stored && VIZ_MODES.includes(stored)) return stored;
		} catch { /* ignore */ }
		return 'waterfall';
	}
	let vizMode: VisualizationMode = $state(loadVizMode());
	$effect(() => {
		try { localStorage.setItem(VIZ_STORAGE_KEY, vizMode); } catch { /* ignore */ }
	});

	// Latest PCM samples for LUFS metering (fed from audio manager)
	let latestPcm: Float32Array | null = $state(null);
	// TX PCM samples (float32) for visualization during transmit
	let txPcm: Float32Array | null = $state(null);
	// FFT bins from client-side mic FFT (simulation mode only)
	let simFftBins: Float32Array | null = $state(null);

	// Active layout from store
	let layout: LayoutConfig = $state($activeLayout);
	$effect(() => {
		layout = $activeLayout;
	});

	function handleControlMessage(msg: object) {
		const m = msg as Record<string, unknown>;
		if (m.freq !== undefined) radio = { ...radio, freq: m.freq as number };
		if (m.mode !== undefined) radio = { ...radio, mode: m.mode as string };
		if (m.ptt !== undefined) radio = { ...radio, ptt: m.ptt as boolean };
		if (m.online !== undefined) radio = { ...radio, online: m.online as boolean };
		if (m.smeter !== undefined) radio = { ...radio, smeter: m.smeter as number };
		if (m.vfo !== undefined) radio = { ...radio, vfo: m.vfo as string };
		if (m.swr !== undefined) radio = { ...radio, swr: m.swr as number };
		if (m.ctcss_tone !== undefined) radio = { ...radio, ctcss_tone: m.ctcss_tone as number };
		radioState.set(radio);
	}

	let mountCleanup: (() => void) | undefined;
	onDestroy(() => mountCleanup?.());

	onMount(async () => {
		// Check setup_required
		try {
			const status = await getStatus();
			if (status.setup_required) {
				await goto('/setup');
				return;
			}

			// Pick first available radio
			const firstRadio = status.radios[0];
			if (!firstRadio) {
				// No active radios but setup was completed — stay on main page
				return;
			}
			radioId = firstRadio.id;
			radio = { ...radio, ...firstRadio };
			radioState.set(radio);
		} catch {
			// Backend unreachable — stay on page, WS will show offline
		}

		// Load config
		try {
			const cfg = await getConfig();
			appConfig.set(cfg);
			region = cfg.operator?.region ?? 'us';
			// Find the first radio's enabled bands
			const radio = cfg.radios?.find((r) => r.id === radioId);
			enabledBands = radio?.bands ?? [];
		} catch {
			// ignore
		}

		// Load presets
		try {
			const result = await getPresets();
			presets = result.presets;
		} catch {
			// ignore — presets optional
		}

		if (!radioId) return;

		// Fetch initial CAT state
		try {
			const cat = await getRadioCat(radioId);
			radio = { ...radio, ...cat };
			radioState.set(radio);
		} catch {
			// ignore — control WS will push state on connect
		}

		// Control WebSocket
		const cws = new ControlWebSocket(radioId, handleControlMessage);
		cws.connect();
		controlWs = cws;

		// Audio setup
		audioMgr = new AudioManager();
		await audioMgr.startRx();
		dspChain = audioMgr.getDspChain();
		rxDspChain = audioMgr.getRxDspChain();

		if (radio.simulation) {
			// Simulated radio: mic is the audio source (RX path)
			audioMgr.onRxPcmFloat = (f32: Float32Array) => { latestPcm = f32; };
			audioMgr.onSimFftBins = (bins: Float32Array) => { simFftBins = bins; };
			await audioMgr.startMicAsRx();

			// Load DSP config for RX chain in simulation mode
			try {
				const dspCfg = await getDspConfig(radioId);
				const rx = rxDspChain;
				if (rx) {
					rx.enableHighpass(dspCfg.rx.highpass_enabled);
					rx.setHighpass(dspCfg.rx.highpass_freq);
					rx.enableLowpass(dspCfg.rx.lowpass_enabled);
					rx.setLowpass(dspCfg.rx.lowpass_freq);
					rx.enablePeak(dspCfg.rx.peak_enabled);
					rx.setPeak(dspCfg.rx.peak_freq, dspCfg.rx.peak_gain, dspCfg.rx.peak_q);
					rx.enableNoiseBlanker(dspCfg.rx.noise_blanker_enabled);
					rx.setNoiseBlankerFreq(dspCfg.rx.noise_blanker_freq as 50 | 60);
					rx.enableNotch(dspCfg.rx.notch_enabled);
					rx.setNotchMode(dspCfg.rx.notch_mode);
					rx.setNotch(dspCfg.rx.notch_freq, dspCfg.rx.notch_q);
					rx.enableBandpass(dspCfg.rx.bandpass_enabled);
					rx.setBandpassPreset(dspCfg.rx.bandpass_preset);
					rx.setBandpass(dspCfg.rx.bandpass_center, dspCfg.rx.bandpass_width);
					rx.enableNr(dspCfg.rx.nr_enabled);
					rx.setNrAmount(dspCfg.rx.nr_amount);
				}
			} catch (e) {
				console.warn('[DSP] Failed to load DSP config from backend, using defaults:', e);
			}

			mountCleanup = () => {
				cws.disconnect();
				audioMgr?.stopRx(); // also calls stopMicAsRx internally
			};
			return;
		}

		// Real radio: server audio via WebSocket
		const aws = new AudioWebSocket(radioId, (buf: ArrayBuffer) => {
			audioMgr?.feedRx(buf);
			// Extract Float32 samples for LUFS metering
			const s16 = new Int16Array(buf);
			const f32 = new Float32Array(s16.length);
			for (let i = 0; i < s16.length; i++) {
				f32[i] = s16[i] / 32768;
			}
			latestPcm = f32;
		});
		audioMgr.onTxChunk = (buf: ArrayBuffer) => {
			aws.sendBinary(buf);
			// Convert s16le to float32 for TX visualization
			const s16 = new Int16Array(buf);
			const f32 = new Float32Array(s16.length);
			for (let i = 0; i < s16.length; i++) {
				f32[i] = s16[i] / 32768;
			}
			txPcm = f32;
		};
		aws.connect();
		audioWs = aws;

		// Start TX capture (mic) alongside RX — PTT gating happens in worklet
		await audioMgr.startTx();
		txDspChain = audioMgr.getTxDspChain();

		// Load DSP config from backend and apply to both chains
		try {
			const dspCfg = await getDspConfig(radioId);
			const rx = rxDspChain;
			if (rx) {
				rx.enableHighpass(dspCfg.rx.highpass_enabled);
				rx.setHighpass(dspCfg.rx.highpass_freq);
				rx.enableLowpass(dspCfg.rx.lowpass_enabled);
				rx.setLowpass(dspCfg.rx.lowpass_freq);
				rx.enablePeak(dspCfg.rx.peak_enabled);
				rx.setPeak(dspCfg.rx.peak_freq, dspCfg.rx.peak_gain, dspCfg.rx.peak_q);
				rx.enableNoiseBlanker(dspCfg.rx.noise_blanker_enabled);
				rx.setNoiseBlankerFreq(dspCfg.rx.noise_blanker_freq as 50 | 60);
				rx.enableNotch(dspCfg.rx.notch_enabled);
				rx.setNotchMode(dspCfg.rx.notch_mode);
				rx.setNotch(dspCfg.rx.notch_freq, dspCfg.rx.notch_q);
				rx.enableBandpass(dspCfg.rx.bandpass_enabled);
				rx.setBandpassPreset(dspCfg.rx.bandpass_preset);
				rx.setBandpass(dspCfg.rx.bandpass_center, dspCfg.rx.bandpass_width);
				rx.enableNr(dspCfg.rx.nr_enabled);
				rx.setNrAmount(dspCfg.rx.nr_amount);
			}
			const tx = txDspChain;
			if (tx) {
				tx.enableHighpass(dspCfg.tx.highpass_enabled);
				tx.setHighpass(dspCfg.tx.highpass_freq);
				tx.enableLowpass(dspCfg.tx.lowpass_enabled);
				tx.setLowpass(dspCfg.tx.lowpass_freq);
				tx.enableEq(dspCfg.tx.eq_enabled);
				tx.setBass(dspCfg.tx.eq_bass_gain);
				tx.setMid(dspCfg.tx.eq_mid_gain);
				tx.setTreble(dspCfg.tx.eq_treble_gain);
				tx.enableCompressor(dspCfg.tx.compressor_enabled);
				if (dspCfg.tx.compressor_preset !== 'off') {
					tx.setCompressorPreset(dspCfg.tx.compressor_preset);
				}
				tx.setCompressor(
					dspCfg.tx.compressor_threshold,
					dspCfg.tx.compressor_ratio,
					dspCfg.tx.compressor_attack,
					dspCfg.tx.compressor_release,
				);
				tx.enableLimiter(dspCfg.tx.limiter_enabled);
				tx.setLimiterThreshold(dspCfg.tx.limiter_threshold);
				tx.enableGate(dspCfg.tx.gate_enabled);
				tx.setGateThreshold(dspCfg.tx.gate_threshold);
			}
		} catch (e) {
			console.warn('[DSP] Failed to load DSP config from backend, using defaults:', e);
		}

		mountCleanup = () => {
			cws.disconnect();
			aws.disconnect();
			audioMgr?.stopTx();
			audioMgr?.stopRx();
		};
	});

	// Narrow screen breakpoint
	let isNarrow = $state(false);

	function getColPanels(col: number): LayoutPanel[] {
		return [...layout.panels]
			.filter((p) => p.position.col === col)
			.sort((a, b) => a.position.row - b.position.row);
	}
	onMount(() => {
		const mq = window.matchMedia('(max-width: 767px)');
		isNarrow = mq.matches;
		const handler = (e: MediaQueryListEvent) => { isNarrow = e.matches; };
		mq.addEventListener('change', handler);
		return () => mq.removeEventListener('change', handler);
	});
</script>

<svelte:head>
	<title>Riglet — {radio.name || 'Radio'}</title>
</svelte:head>

<!-- Skip to content link for keyboard users -->
<a href="#main-content" class="skip-link">Skip to main content</a>

<div class="app">
	<header class="topbar">
		<span class="brand">Riglet</span>
		{#if radio.name}
			<span class="radio-name">{radio.name}</span>
		{/if}
		<span
			class="status-pill"
			class:online={radio.online}
			class:offline={!radio.online}
			role="status"
			aria-live="polite"
			aria-label={`Radio ${radio.online ? (radio.simulation ? 'simulation mode' : 'online') : 'offline'}`}
		>
			{radio.online ? (radio.simulation ? 'SIM' : 'ONLINE') : 'OFFLINE'}
		</span>
		<LayoutManager />
		<a href="/setup" class="setup-btn" title="Open setup wizard" aria-label="Setup / configuration">⚙</a>
	</header>

	<main id="main-content" tabindex="-1">
		{#if radioId}
			{#if isNarrow}
				<!-- Narrow / single-column fallback -->
				<div class="narrow-layout">
					<div class="control-block">
						<ModeSelector mode={radio.mode} {controlWs} {radioId} />
					</div>
					<div class="control-block freq-knob-row">
						<AudioControls {radioId} {rxVolume} {txGain} audioManager={audioMgr} />
						<FrequencyDisplay freq={radio.freq} {controlWs} {presets} />
						<TuningKnob freq={radio.freq} {controlWs} />
					</div>
					<div class="control-block">
						<BandSelector {controlWs} currentFreq={radio.freq} {region} {enabledBands} />
					</div>
					<div class="control-block">
						<PresetSelector {radioId} currentFreqMhz={radio.freq} {controlWs} onPresetsChange={(p) => { presets = p; }} />
					</div>
					<VisualizationPanel bind:mode={vizMode} {radioId} cursorMhz={radio.freq} radioMode={radio.mode} pcmSamples={radio.ptt ? txPcm : latestPcm} fftBins={simFftBins} />
					<div class="control-block ptt-row">
						<PttButton ptt={radio.ptt} {controlWs} />
						<Knob value={txGain} min={0} max={100} step={5} label="Mic Gain" size={72} onchange={onTxGainChange} />
					</div>
					<div class="control-block">
						<SmeterDisplay smeter={radio.smeter ?? 0} />
					</div>
					<div class="control-block">
						<DspPanel dspChain={dspChain} />
					</div>
				</div>
			{:else}
				<!-- Dynamic layout: outer grid sets column widths; each column scrolls independently -->
				<div
					class="layout-grid"
					style="grid-template-columns: {layout.columnWidths ?? `repeat(${layout.columns}, 1fr)`};"
					aria-label="Radio control layout"
				>
					{#each Array.from({ length: layout.columns }, (_, i) => i + 1) as col}
					<div class="layout-col">
					{#each getColPanels(col) as panel (panel.id)}
						<div
							class="layout-panel"
							class:viz-panel={panel.component === 'visualization'}
						>
							{#if panel.component === 'visualization'}
								<VisualizationPanel bind:mode={vizMode} {radioId} cursorMhz={radio.freq} radioMode={radio.mode} pcmSamples={radio.ptt ? txPcm : latestPcm} fftBins={simFftBins} />
							{:else if panel.component === 'frequency'}
								<div class="inner-block freq-knob-row">
									<AudioControls {radioId} {rxVolume} {txGain} audioManager={audioMgr} />
									<FrequencyDisplay freq={radio.freq} {controlWs} {presets} />
									<TuningKnob freq={radio.freq} {controlWs} />
								</div>
							{:else if panel.component === 'band-selector'}
								<div class="inner-block">
									<BandSelector {controlWs} currentFreq={radio.freq} {region} {enabledBands} />
								</div>
							{:else if panel.component === 'mode-selector'}
								<div class="inner-block">
									<ModeSelector mode={radio.mode} {controlWs} {radioId} />
								</div>
							{:else if panel.component === 'ptt'}
								<div class="inner-block ptt-row">
									<PttButton ptt={radio.ptt} {controlWs} />
									<Knob value={txGain} min={0} max={100} step={5} label="Mic Gain" size={72} onchange={onTxGainChange} />
								</div>
							{:else if panel.component === 'smeter'}
								<div class="inner-block">
									<SmeterDisplay smeter={radio.smeter ?? 0} />
								</div>
							{:else if panel.component === 'audio'}
								<div class="inner-block">
									<AudioControls {radioId} {rxVolume} {txGain} audioManager={audioMgr} />
								</div>
							{:else if panel.component === 'dsp'}
								<div class="inner-block">
									<DspPanel dspChain={dspChain} />
								</div>
							{:else if panel.component === 'lufs-meter'}
								<div class="inner-block">
									<LufsMeter pcmSamples={latestPcm} />
								</div>
							{:else if panel.component === 'presets'}
								<div class="inner-block">
									<PresetSelector {radioId} currentFreqMhz={radio.freq} {controlWs} onPresetsChange={(p) => { presets = p; }} />
								</div>
							{:else if panel.component === 'vfo'}
								<div class="inner-block">
									<VfoSelector vfo={radio.vfo ?? 'VFOA'} {controlWs} />
								</div>
							{:else if panel.component === 'cat-extended'}
								<div class="inner-block">
									<CatExtended
										vfo={radio.vfo ?? 'VFOA'}
										swr={radio.swr ?? 1.0}
										ctcssTone={radio.ctcss_tone ?? 0}
										ptt={radio.ptt}
										{controlWs}
									/>
								</div>
								{/if}
						</div>
					{/each}
					</div><!-- /.layout-col -->
				{/each}<!-- /columns loop -->
				</div><!-- /.layout-grid -->
			{/if}
		{:else}
			<div class="no-radio">
				<p>No radio configured. <a href="/setup">Run setup wizard</a></p>
			</div>
		{/if}
	</main>

	<footer class="footer">
		Thoughtfully made by <a href="https://tholent.com" target="_blank" rel="noopener noreferrer">tholent</a>
	</footer>
</div>

<style>
	.skip-link {
		position: absolute;
		top: -100%;
		left: 0;
		background: #4a9eff;
		color: #000;
		padding: 8px 16px;
		font-weight: 700;
		z-index: 9999;
		text-decoration: none;
		border-radius: 0 0 4px 0;
	}

	.skip-link:focus {
		top: 0;
	}

	:global(body) {
		margin: 0;
		background: #0d0d0d;
		color: #e0e0e0;
		font-family: system-ui, sans-serif;
	}

	.app {
		height: 100vh;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.topbar {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 10px 20px;
		background: #1a1a1a;
		border-bottom: 1px solid #333;
	}

	.brand {
		font-weight: 700;
		font-size: 1.1rem;
		color: #4a9eff;
	}

	.radio-name {
		color: #ccc;
		font-size: 0.95rem;
	}

	.status-pill {
		margin-left: auto;
		padding: 3px 10px;
		border-radius: 12px;
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		border: 1px solid #444;
		color: #888;
	}

	.status-pill.online { border-color: #4caf50; color: #4caf50; }
	.status-pill.offline { border-color: #f44336; color: #f44336; }

	main {
		flex: 1;
		min-height: 0;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}

	main:focus {
		outline: none;
	}

	/* Dynamic layout grid — columns only; rows handled per-column */
	.layout-grid {
		display: grid;
		gap: 0;
		flex: 1;
		min-height: 0;
		overflow: hidden;
		align-items: stretch;
	}

	/* Each column scrolls independently */
	.layout-col {
		display: flex;
		flex-direction: column;
		min-height: 0;
		overflow-y: auto;
		overflow-x: hidden;
		scrollbar-width: thin;
		scrollbar-color: #2a2a2a transparent;
	}

	.layout-panel {
		min-height: 0;
		flex-shrink: 0;
		display: flex;
		flex-direction: column;
	}

	/* Visualization panel fills remaining column height */
	.layout-panel.viz-panel {
		flex: 1;
		min-height: 200px;
	}

	/* Panels that are not the visualization get block padding */
	.inner-block {
		background: #1a1a1a;
		border: 1px solid #2a2a2a;
		border-radius: 0;
		padding: 10px 12px;
		height: 100%;
		box-sizing: border-box;
	}

	.ptt-row {
		display: flex;
		align-items: center;
		gap: 16px;
	}

	.freq-knob-row {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	/* Narrow single-column fallback */
	.narrow-layout {
		display: flex;
		flex-direction: column;
		gap: 0;
		flex: 1;
		overflow-y: auto;
	}

	.control-block {
		background: #1a1a1a;
		border-bottom: 1px solid #2a2a2a;
		padding: 10px 12px;
	}

	.no-radio {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		color: #888;
	}

	.no-radio a { color: #4a9eff; }

	.footer {
		flex-shrink: 0;
		padding: 6px 20px;
		background: #1a1a1a;
		border-top: 1px solid #2a2a2a;
		font-size: 0.7rem;
		color: #555;
		text-align: center;
	}

	.footer a {
		color: #4a9eff;
		text-decoration: none;
	}

	.footer a:hover {
		text-decoration: underline;
	}

	.setup-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		border: 1px solid #444;
		border-radius: 4px;
		background: #1a1a1a;
		color: #888;
		font-size: 1rem;
		text-decoration: none;
		transition: border-color 0.1s, color 0.1s;
	}

	.setup-btn:hover {
		border-color: #666;
		color: #ccc;
	}

	.setup-btn:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
	}

	@media (prefers-reduced-motion: reduce) {
		* {
			animation-duration: 0.01ms !important;
			animation-iteration-count: 1 !important;
			transition-duration: 0.01ms !important;
		}
	}
</style>
