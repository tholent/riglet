<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { getStatus, getConfig, getRadioCat, getPresets } from '$lib/api.js';
	import { radioState, appConfig } from '$lib/stores.js';
	import { ControlWebSocket, AudioWebSocket } from '$lib/websocket.js';
	import { AudioManager } from '$lib/audio/audio-manager.js';
	import { activeLayout } from '$lib/layout/store.js';
	import type { LayoutConfig } from '$lib/layout/types.js';
	import VisualizationPanel from '$lib/components/VisualizationPanel.svelte';
	import FrequencyDisplay from '$lib/components/FrequencyDisplay.svelte';
	import BandSelector from '$lib/components/BandSelector.svelte';
	import ModeSelector from '$lib/components/ModeSelector.svelte';
	import PttButton from '$lib/components/PttButton.svelte';
	import SmeterDisplay from '$lib/components/SmeterDisplay.svelte';
	import AudioControls from '$lib/components/AudioControls.svelte';
	import LufsMeter from '$lib/components/LufsMeter.svelte';
	import DspPanel from '$lib/components/DspPanel.svelte';
	import PresetSelector from '$lib/components/PresetSelector.svelte';
	import VfoSelector from '$lib/components/VfoSelector.svelte';
	import CatExtended from '$lib/components/CatExtended.svelte';
	import LayoutManager from '$lib/components/LayoutManager.svelte';
	import VizSwitcher from '$lib/components/VizSwitcher.svelte';
	import type { VisualizationMode } from '$lib/viz/types.js';
	import type { RadioState, PresetConfig } from '$lib/types.js';

	let radioId = $state<string | null>(null);
	let state = $state<RadioState>({
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

	let controlWs = $state<ControlWebSocket | null>(null);
	let audioWs: AudioWebSocket | null = null;
	let audioMgr = $state<AudioManager | null>(null);

	// Presets
	let presets = $state<PresetConfig[]>([]);

	// Region and enabled bands from config
	let region = $state('us');
	let enabledBands = $state<string[]>([]);

	// Visualization mode
	let vizMode = $state<VisualizationMode>('waterfall');

	// Latest PCM samples for LUFS metering (fed from audio manager)
	let latestPcm = $state<Float32Array | null>(null);
	// TX PCM samples (float32) for visualization during transmit
	let txPcm = $state<Float32Array | null>(null);

	// Active layout from store
	let layout = $state<LayoutConfig>($activeLayout);
	$effect(() => {
		layout = $activeLayout;
	});

	function handleControlMessage(msg: object) {
		const m = msg as Record<string, unknown>;
		if (m.freq !== undefined) state = { ...state, freq: m.freq as number };
		if (m.mode !== undefined) state = { ...state, mode: m.mode as string };
		if (m.ptt !== undefined) state = { ...state, ptt: m.ptt as boolean };
		if (m.online !== undefined) state = { ...state, online: m.online as boolean };
		if (m.smeter !== undefined) state = { ...state, smeter: m.smeter as number };
		if (m.vfo !== undefined) state = { ...state, vfo: m.vfo as string };
		if (m.swr !== undefined) state = { ...state, swr: m.swr as number };
		if (m.ctcss_tone !== undefined) state = { ...state, ctcss_tone: m.ctcss_tone as number };
		radioState.set(state);
	}

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
			state = { ...state, ...firstRadio };
			radioState.set(state);
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
			state = { ...state, ...cat };
			radioState.set(state);
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

		return () => {
			cws.disconnect();
			aws.disconnect();
			audioMgr?.stopTx();
			audioMgr?.stopRx();
		};
	});

	// Narrow screen breakpoint
	let isNarrow = $state(false);
	onMount(() => {
		const mq = window.matchMedia('(max-width: 767px)');
		isNarrow = mq.matches;
		const handler = (e: MediaQueryListEvent) => { isNarrow = e.matches; };
		mq.addEventListener('change', handler);
		return () => mq.removeEventListener('change', handler);
	});
</script>

<svelte:head>
	<title>Riglet — {state.name || 'Radio'}</title>
</svelte:head>

<!-- Skip to content link for keyboard users -->
<a href="#main-content" class="skip-link">Skip to main content</a>

<div class="app">
	<header class="topbar" role="banner">
		<span class="brand">Riglet</span>
		{#if state.name}
			<span class="radio-name">{state.name}</span>
		{/if}
		<span
			class="status-pill"
			class:online={state.online}
			class:offline={!state.online}
			role="status"
			aria-live="polite"
			aria-label={`Radio ${state.online ? (state.simulation ? 'simulation mode' : 'online') : 'offline'}`}
		>
			{state.online ? (state.simulation ? 'SIM' : 'ONLINE') : 'OFFLINE'}
		</span>
		<VizSwitcher bind:mode={vizMode} />
		<LayoutManager />
		<a href="/setup" class="setup-btn" title="Open setup wizard" aria-label="Setup / configuration">⚙</a>
	</header>

	<main id="main-content" tabindex="-1">
		{#if radioId}
			{#if isNarrow}
				<!-- Narrow / single-column fallback -->
				<div class="narrow-layout">
					<div class="control-block">
						<ModeSelector mode={state.mode} {controlWs} {radioId} />
					</div>
					<div class="control-block">
						<FrequencyDisplay freq={state.freq} {controlWs} {presets} />
					</div>
					<div class="control-block">
						<BandSelector {controlWs} currentFreq={state.freq} {region} {enabledBands} />
					</div>
					<div class="control-block">
						<PresetSelector {radioId} currentFreqMhz={state.freq} {controlWs} />
					</div>
					<VisualizationPanel mode={vizMode} {radioId} cursorMhz={state.freq} radioMode={state.mode} pcmSamples={state.ptt ? txPcm : latestPcm} />
					<div class="control-block">
						<PttButton ptt={state.ptt} {controlWs} />
					</div>
					<div class="control-block">
						<SmeterDisplay smeter={state.smeter ?? 0} />
					</div>
					<div class="control-block">
						<AudioControls {radioId} {rxVolume} {txGain} audioManager={audioMgr} />
					</div>
					<div class="control-block">
						<DspPanel dspChain={audioMgr?.getDspChain() ?? null} />
					</div>
				</div>
			{:else}
				<!-- Dynamic CSS Grid driven by active LayoutConfig -->
				<div
					class="layout-grid"
					style="
						grid-template-columns: {layout.columnWidths ?? `repeat(${layout.columns}, 1fr)`};
						grid-template-rows: repeat({layout.rows}, auto);
					"
					aria-label="Radio control layout"
				>
					{#each layout.panels as panel (panel.id)}
						<div
							class="layout-panel"
							style="
								grid-column: {panel.position.col} / span {panel.position.colSpan};
								grid-row: {panel.position.row} / span {panel.position.rowSpan};
							"
						>
							{#if panel.component === 'visualization'}
								<VisualizationPanel mode={vizMode} {radioId} cursorMhz={state.freq} radioMode={state.mode} pcmSamples={state.ptt ? txPcm : latestPcm} />
							{:else if panel.component === 'frequency'}
								<div class="inner-block">
									<FrequencyDisplay freq={state.freq} {controlWs} {presets} />
								</div>
							{:else if panel.component === 'band-selector'}
								<div class="inner-block">
									<BandSelector {controlWs} currentFreq={state.freq} {region} {enabledBands} />
								</div>
							{:else if panel.component === 'mode-selector'}
								<div class="inner-block">
									<ModeSelector mode={state.mode} {controlWs} {radioId} />
								</div>
							{:else if panel.component === 'ptt'}
								<div class="inner-block">
									<PttButton ptt={state.ptt} {controlWs} />
								</div>
							{:else if panel.component === 'smeter'}
								<div class="inner-block">
									<SmeterDisplay smeter={state.smeter ?? 0} />
								</div>
							{:else if panel.component === 'audio'}
								<div class="inner-block">
									<AudioControls {radioId} {rxVolume} {txGain} audioManager={audioMgr} />
								</div>
							{:else if panel.component === 'dsp'}
								<div class="inner-block">
									<DspPanel dspChain={audioMgr?.getDspChain() ?? null} />
								</div>
							{:else if panel.component === 'lufs-meter'}
								<div class="inner-block">
									<LufsMeter pcmSamples={latestPcm} />
								</div>
							{:else if panel.component === 'presets'}
								<div class="inner-block">
									<PresetSelector {radioId} currentFreqMhz={state.freq} {controlWs} />
								</div>
							{:else if panel.component === 'vfo'}
								<div class="inner-block">
									<VfoSelector vfo={state.vfo ?? 'VFOA'} {controlWs} />
								</div>
							{:else if panel.component === 'cat-extended'}
								<div class="inner-block">
									<CatExtended
										vfo={state.vfo ?? 'VFOA'}
										swr={state.swr ?? 1.0}
										ctcssTone={state.ctcss_tone ?? 0}
										ptt={state.ptt}
										{controlWs}
									/>
								</div>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		{:else}
			<div class="no-radio">
				<p>No radio configured. <a href="/setup">Run setup wizard</a></p>
			</div>
		{/if}
	</main>
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

	/* Dynamic layout grid */
	.layout-grid {
		display: grid;
		gap: 0;
		flex: 1;
		min-height: 0;
		overflow: hidden;
	}

	.layout-panel {
		min-height: 0;
		overflow: hidden;
		display: flex;
		flex-direction: column;
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
