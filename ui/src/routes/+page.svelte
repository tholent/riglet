<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { getStatus, getConfig, getRadioCat, getPresets, postAudioVolume, getDspConfig, getAuthStatus, postLogout } from '$lib/api.js';
	import type { RxDspConfig, TxDspConfig } from '$lib/api.js';
	import { DspPersistence } from '$lib/dsp-persistence.js';
	import { radioState, appConfig, theme } from '$lib/stores.js';
	import { setTheme } from '$lib/theme.js';
	import { ControlWebSocket, AudioWebSocket } from '$lib/websocket.js';
	import { AudioManager } from '$lib/audio/audio-manager.js';
	import { activeLayout } from '$lib/layout/store.js';
	import type { LayoutConfig, LayoutPanel } from '$lib/layout/types.js';
	import VisualizationPanel from '$lib/components/VisualizationPanel.svelte';
	import FrequencyDisplay from '$lib/components/FrequencyDisplay.svelte';
	import BandSelector from '$lib/components/BandSelector.svelte';
	import ModeSelector from '$lib/components/ModeSelector.svelte';
	import PttPanel from '$lib/components/PttPanel.svelte';
	import AudioControls from '$lib/components/AudioControls.svelte';
	import RxDspPillRow from '$lib/components/RxDspPillRow.svelte';
	import PresetSelector from '$lib/components/PresetSelector.svelte';
	import VfoSelector from '$lib/components/VfoSelector.svelte';
	import CatExtended from '$lib/components/CatExtended.svelte';
	import TuningKnob from '$lib/components/TuningKnob.svelte';
	import LayoutManager from '$lib/components/LayoutManager.svelte';
	import type { VisualizationMode } from '$lib/viz/types.js';
	import type { RadioState, PresetConfig } from '$lib/types.js';
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
		tuning: false,
		tuner_enabled: false,
	});
	let rxVolume = $state(50);
	let txGain = $state(50);

	// Tracks the *resolved* theme ('dark' | 'light') — the store may hold 'system'.
	let resolvedTheme = $state<'dark' | 'light'>('dark');

	function toggleTheme() {
		const next = resolvedTheme === 'dark' ? 'light' : 'dark';
		setTheme(next);
		theme.set(next);
		resolvedTheme = next;
	}

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
		if (!dspPersistence) return;
		// Build a partial RxDspConfig patch from the changed fields
		const patch: Partial<RxDspConfig> = detail as Partial<RxDspConfig>;
		dspPersistence.saveRx(patch);
	}

	function applyRxDspConfig(rx: RxDspChain, cfg: RxDspConfig): void {
		rx.enableHighpass(cfg.highpass_enabled);
		rx.setHighpass(cfg.highpass_freq);
		rx.enableLowpass(cfg.lowpass_enabled);
		rx.setLowpass(cfg.lowpass_freq);
		rx.enablePeak(cfg.peak_enabled);
		rx.setPeak(cfg.peak_freq, cfg.peak_gain, cfg.peak_q);
		rx.enableNoiseBlanker(cfg.noise_blanker_enabled);
		rx.setNoiseBlankerFreq(cfg.noise_blanker_freq as 50 | 60);
		rx.enableNotch(cfg.notch_enabled);
		rx.setNotchMode(cfg.notch_mode);
		rx.setNotch(cfg.notch_freq, cfg.notch_q);
		rx.enableBandpass(cfg.bandpass_enabled);
		rx.setBandpassPreset(cfg.bandpass_preset);
		rx.setBandpass(cfg.bandpass_center, cfg.bandpass_width);
		rx.enableNr(cfg.nr_enabled);
		rx.setNrAmount(cfg.nr_amount);
	}

	function applyTxDspConfig(tx: TxDspChain, cfg: TxDspConfig): void {
		tx.enableHighpass(cfg.highpass_enabled);
		tx.setHighpass(cfg.highpass_freq);
		tx.enableLowpass(cfg.lowpass_enabled);
		tx.setLowpass(cfg.lowpass_freq);
		tx.enableEq(cfg.eq_enabled);
		tx.setBass(cfg.eq_bass_gain);
		tx.setMid(cfg.eq_mid_gain);
		tx.setTreble(cfg.eq_treble_gain);
		tx.enableCompressor(cfg.compressor_enabled);
		if (cfg.compressor_preset !== 'off') {
			tx.setCompressorPreset(cfg.compressor_preset);
		}
		tx.setCompressor(
			cfg.compressor_threshold,
			cfg.compressor_ratio,
			cfg.compressor_attack,
			cfg.compressor_release,
		);
		tx.enableLimiter(cfg.limiter_enabled);
		tx.setLimiterThreshold(cfg.limiter_threshold);
		tx.enableGate(cfg.gate_enabled);
		tx.setGateThreshold(cfg.gate_threshold);
	}

	function handleTxDspChange(detail: Record<string, unknown>): void {
		const param = detail.param as string;
		const value = detail.value;
		if (param === 'mic_mute') {
			audioMgr?.setMicMute(value as boolean);
			return;
		}
		if (!dspPersistence) return;
		const patch: Partial<TxDspConfig> = { [param]: value } as Partial<TxDspConfig>;
		dspPersistence.saveTx(patch);
	}

	let controlWs: ControlWebSocket | null = $state(null);
	let audioWs: AudioWebSocket | null = null;
	let audioMgr: AudioManager | null = $state(null);
	let rxDspChain: RxDspChain | null = $state(null);
	let txDspChain: TxDspChain | null = $state(null);
	let dspPersistence: DspPersistence | null = null;

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
		if (m.smeter_s !== undefined) radio = { ...radio, smeter: m.smeter_s as number };
		if (m.vfo !== undefined) radio = { ...radio, vfo: m.vfo as string };
		if (m.swr !== undefined) radio = { ...radio, swr: m.swr as number };
		if (m.ctcss_tone !== undefined) radio = { ...radio, ctcss_tone: m.ctcss_tone as number };
		if (m.rf_gain !== undefined) radio = { ...radio, rf_gain: m.rf_gain as number };
		if (m.squelch !== undefined) radio = { ...radio, squelch: m.squelch as number };
		if (m.tuning !== undefined) radio = { ...radio, tuning: m.tuning as boolean };
		if (m.tuner_enabled !== undefined) radio = { ...radio, tuner_enabled: m.tuner_enabled as boolean };
		radioState.set(radio);
	}

	let mountCleanup: (() => void) | undefined;
	onDestroy(() => mountCleanup?.());

	async function handleLogout() {
		await postLogout();
		await goto('/login');
	}

	onMount(async () => {
		// Sync resolved theme from data-theme attribute set by initTheme() in layout
		resolvedTheme = (document.documentElement.getAttribute('data-theme') ?? 'dark') as 'dark' | 'light';

		// Auth guard
		try {
			const auth = await getAuthStatus();
			if (auth.password_set && !auth.authenticated) {
				await goto('/login');
				return;
			}
		} catch {
			// backend unreachable — continue
		}

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
		rxDspChain = audioMgr.getRxDspChain();

		if (radio.simulation) {
			// Simulated radio: mic is the audio source (RX path)
			audioMgr.onRxPcmFloat = (f32: Float32Array) => { latestPcm = f32; };
			// getFloatFrequencyData returns dBFS (~-100 to 0); renderers handle dB values directly
			audioMgr.onSimFftBins = (bins: Float32Array) => { simFftBins = bins; };
			await audioMgr.startMicAsRx();

			// Start TX DSP chain so controls are available even in simulation
			await audioMgr.startTx();
			txDspChain = audioMgr.getTxDspChain();

			// Load DSP config for both chains in simulation mode
			try {
				const dspCfg = await getDspConfig(radioId);
				const rx = rxDspChain;
				if (rx) applyRxDspConfig(rx, dspCfg.rx);
				const tx = txDspChain;
				if (tx) applyTxDspConfig(tx, dspCfg.tx);
			} catch (e) {
				console.warn('[DSP] Failed to load DSP config from backend, using defaults:', e);
			}

			dspPersistence = new DspPersistence(radioId);

			mountCleanup = () => {
				cws.disconnect();
				audioMgr?.stopRx(); // also calls stopMicAsRx internally
				dspPersistence?.destroy();
				dspPersistence = null;
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
			if (rxDspChain) applyRxDspConfig(rxDspChain, dspCfg.rx);
			if (txDspChain) applyTxDspConfig(txDspChain, dspCfg.tx);
		} catch (e) {
			console.warn('[DSP] Failed to load DSP config from backend, using defaults:', e);
		}

		dspPersistence = new DspPersistence(radioId);

		mountCleanup = () => {
			cws.disconnect();
			aws.disconnect();
			audioMgr?.stopTx();
			audioMgr?.stopRx();
			dspPersistence?.destroy();
			dspPersistence = null;
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
		<button
			class="theme-btn"
			onclick={toggleTheme}
			title={resolvedTheme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
			aria-label={resolvedTheme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
		>{resolvedTheme === 'dark' ? '☀' : '☾'}</button>
		<a href="/setup" class="setup-btn" title="Open setup wizard" aria-label="Setup / configuration">⚙</a>
		<button
			class="theme-btn"
			onclick={handleLogout}
			title="Log out"
			aria-label="Log out"
		>out</button>
	</header>

	<main id="main-content" tabindex="-1">
		{#if radioId}
			{#if isNarrow}
				<!-- Narrow / single-column fallback -->
				<div class="narrow-layout">
					<div class="control-block">
						<ModeSelector mode={radio.mode} {controlWs} {radioId} />
					</div>
					<div class="control-block">
						<div class="freq-knob-row">
							<AudioControls {radioId} {rxVolume} {txGain} audioManager={audioMgr} rfGain={radio.rf_gain ?? 50} squelch={radio.squelch ?? 0} mode={radio.mode} {controlWs} ptt={radio.ptt} tuning={radio.tuning ?? false} tunerEnabled={radio.tuner_enabled ?? false} swr={radio.swr ?? 1.0} />
							<div class="freq-dsp-col">
								<FrequencyDisplay freq={radio.freq} {controlWs} {presets} />
								<RxDspPillRow {rxDspChain} on:change={(e) => handleRxDspChange(e.detail)} />
							</div>
							<TuningKnob freq={radio.freq} {controlWs} />
						</div>
					</div>
					<div class="control-block">
						<BandSelector {controlWs} currentFreq={radio.freq} {region} {enabledBands} />
					</div>
					<div class="control-block">
						<PresetSelector {radioId} currentFreqMhz={radio.freq} {controlWs} onPresetsChange={(p) => { presets = p; }} />
					</div>
					<VisualizationPanel bind:mode={vizMode} {radioId} smeter={radio.smeter ?? 0} cursorMhz={radio.freq} radioMode={radio.mode} pcmSamples={radio.ptt ? txPcm : latestPcm} fftBins={simFftBins} />
					<PttPanel
						ptt={radio.ptt}
						{controlWs}
						{txGain}
						{txDspChain}
						txPcm={txPcm}
						{onTxGainChange}
						onTxDspChange={handleTxDspChange}
					/>
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
							class:preset-panel={panel.component === 'presets'}
						>
							{#if panel.component === 'visualization'}
								<VisualizationPanel bind:mode={vizMode} {radioId} smeter={radio.smeter ?? 0} cursorMhz={radio.freq} radioMode={radio.mode} pcmSamples={radio.ptt ? txPcm : latestPcm} fftBins={simFftBins} />
							{:else if panel.component === 'frequency'}
								<div class="inner-block">
									<div class="freq-knob-row">
										<AudioControls {radioId} {rxVolume} {txGain} audioManager={audioMgr} rfGain={radio.rf_gain ?? 50} squelch={radio.squelch ?? 0} mode={radio.mode} {controlWs} ptt={radio.ptt} tuning={radio.tuning ?? false} tunerEnabled={radio.tuner_enabled ?? false} swr={radio.swr ?? 1.0} />
										<div class="freq-dsp-col">
											<FrequencyDisplay freq={radio.freq} {controlWs} {presets} />
											<RxDspPillRow {rxDspChain} on:change={(e) => handleRxDspChange(e.detail)} />
										</div>
										<TuningKnob freq={radio.freq} {controlWs} />
									</div>
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
								<PttPanel
									ptt={radio.ptt}
									{controlWs}
									{txGain}
									{txDspChain}
									txPcm={txPcm}
									{onTxGainChange}
									onTxDspChange={handleTxDspChange}
								/>
							{:else if panel.component === 'smeter'}
								<!-- S-meter is now the sidebar of VisualizationPanel -->
							{:else if panel.component === 'audio'}
								<div class="inner-block">
									<AudioControls {radioId} {rxVolume} {txGain} audioManager={audioMgr} rfGain={radio.rf_gain ?? 50} squelch={radio.squelch ?? 0} mode={radio.mode} {controlWs} ptt={radio.ptt} tuning={radio.tuning ?? false} tunerEnabled={radio.tuner_enabled ?? false} swr={radio.swr ?? 1.0} />
								</div>
							{:else if panel.component === 'dsp'}
								<!-- legacy dsp panel removed -->
							{:else if panel.component === 'lufs-meter'}
								<!-- LUFS meter is now part of PttPanel -->
							{:else if panel.component === 'presets'}
								<div class="inner-block preset-inner">
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
		background: var(--bg-primary);
		color: var(--text-primary);
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
		background: var(--bg-secondary);
		border-bottom: 1px solid var(--border-primary);
	}

	.brand {
		font-weight: 700;
		font-size: 1.1rem;
		color: var(--accent);
	}

	.radio-name {
		color: var(--text-secondary);
		font-size: 0.95rem;
	}

	.status-pill {
		margin-left: auto;
		padding: 3px 10px;
		border-radius: 12px;
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		border: 1px solid var(--border-primary);
		color: var(--text-muted);
	}

	.status-pill.online { border-color: var(--online-color); color: var(--online-color); }
	.status-pill.offline { border-color: var(--offline-color); color: var(--offline-color); }

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
		scrollbar-color: var(--border-primary) transparent;
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

	/* Preset panel fills remaining column height */
	.layout-panel.preset-panel {
		flex: 1;
		min-height: 80px;
		display: flex;
		flex-direction: column;
	}

	/* Panels that are not the visualization get block padding */
	.inner-block {
		background: var(--bg-secondary);
		border: 1px solid var(--border-primary);
		border-radius: 0;
		padding: 10px 12px;
		height: 100%;
		box-sizing: border-box;
	}

	.inner-block.preset-inner {
		display: flex;
		flex-direction: column;
	}

	.freq-knob-row {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.freq-dsp-col {
		display: flex;
		flex-direction: column;
		align-items: center;
		flex: 1;
		min-width: 0;
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
		background: var(--bg-secondary);
		border-bottom: 1px solid var(--border-primary);
		padding: 10px 12px;
	}

	.no-radio {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--text-muted);
	}

	.no-radio a { color: var(--accent); }

	.footer {
		flex-shrink: 0;
		padding: 6px 20px;
		background: var(--bg-secondary);
		border-top: 1px solid var(--border-primary);
		font-size: 0.7rem;
		color: var(--text-muted);
		text-align: center;
	}

	.footer a {
		color: var(--accent);
		text-decoration: none;
	}

	.footer a:hover {
		text-decoration: underline;
	}

	.theme-btn,
	.setup-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		border: 1px solid var(--border-primary);
		border-radius: 4px;
		background: var(--bg-secondary);
		color: var(--text-muted);
		font-size: 1rem;
		text-decoration: none;
		transition: border-color 0.1s, color 0.1s;
	}

	.theme-btn {
		cursor: pointer;
	}

	.theme-btn:hover,
	.setup-btn:hover {
		border-color: var(--text-secondary);
		color: var(--text-primary);
	}

	.theme-btn:focus-visible,
	.setup-btn:focus-visible {
		outline: 2px solid var(--accent);
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
