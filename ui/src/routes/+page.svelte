<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { getStatus, getConfig, getRadioCat } from '$lib/api.js';
	import { radioState, appConfig } from '$lib/stores.js';
	import { ControlWebSocket, AudioWebSocket } from '$lib/websocket.js';
	import { AudioManager } from '$lib/audio/audio-manager.js';
	import Waterfall from '$lib/components/Waterfall.svelte';
	import FrequencyDisplay from '$lib/components/FrequencyDisplay.svelte';
	import ModeSelector from '$lib/components/ModeSelector.svelte';
	import PttButton from '$lib/components/PttButton.svelte';
	import SmeterDisplay from '$lib/components/SmeterDisplay.svelte';
	import AudioControls from '$lib/components/AudioControls.svelte';
	import type { RadioState } from '$lib/types.js';

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
	});
	let rxVolume = $state(50);
	let txGain = $state(50);

	let controlWs = $state<ControlWebSocket | null>(null);
	let audioWs: AudioWebSocket | null = null;
	let audioMgr = $state<AudioManager | null>(null);

	function handleControlMessage(msg: object) {
		const m = msg as Record<string, unknown>;
		if (m.freq !== undefined) state = { ...state, freq: m.freq as number };
		if (m.mode !== undefined) state = { ...state, mode: m.mode as string };
		if (m.ptt !== undefined) state = { ...state, ptt: m.ptt as boolean };
		if (m.online !== undefined) state = { ...state, online: m.online as boolean };
		if (m.smeter !== undefined) state = { ...state, smeter: m.smeter as number };
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
				await goto('/setup');
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
		} catch {
			// ignore
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
		});
		audioMgr.onTxChunk = (buf: ArrayBuffer) => {
			aws.sendBinary(buf);
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
</script>

<svelte:head>
	<title>Riglet — {state.name || 'Radio'}</title>
</svelte:head>

<div class="app">
	<header class="topbar">
		<span class="brand">Riglet</span>
		{#if state.name}
			<span class="radio-name">{state.name}</span>
		{/if}
		<span class="status-pill" class:online={state.online} class:offline={!state.online}>
			{state.online ? (state.simulation ? 'SIM' : 'ONLINE') : 'OFFLINE'}
		</span>
	</header>

	{#if radioId}
		<div class="main-grid">
			<!-- Left column: waterfall -->
			<section class="waterfall-col">
				<Waterfall {radioId} />
			</section>

			<!-- Right column: controls -->
			<section class="controls-col">
				<div class="control-block">
					<FrequencyDisplay freq={state.freq} {controlWs} />
				</div>

				<div class="control-block mode-ptt-row">
					<ModeSelector mode={state.mode} {controlWs} />
					<PttButton ptt={state.ptt} {controlWs} />
				</div>

				<div class="control-block">
					<SmeterDisplay smeter={state.smeter ?? 0} />
				</div>

				<div class="control-block">
					<AudioControls
						{radioId}
						{rxVolume}
						{txGain}
						audioManager={audioMgr}
					/>
				</div>
			</section>
		</div>
	{:else}
		<div class="no-radio">
			<p>No radio configured. <a href="/setup">Run setup wizard</a></p>
		</div>
	{/if}
</div>

<style>
	:global(body) {
		margin: 0;
		background: #0d0d0d;
		color: #e0e0e0;
		font-family: system-ui, sans-serif;
	}

	.app {
		min-height: 100vh;
		display: flex;
		flex-direction: column;
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

	.main-grid {
		display: grid;
		grid-template-columns: 1fr 360px;
		gap: 0;
		flex: 1;
	}

	.waterfall-col {
		padding: 16px;
		border-right: 1px solid #222;
	}

	.controls-col {
		padding: 16px;
		display: flex;
		flex-direction: column;
		gap: 16px;
		overflow-y: auto;
	}

	.control-block {
		background: #1a1a1a;
		border: 1px solid #2a2a2a;
		border-radius: 6px;
		padding: 14px;
	}

	.mode-ptt-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		flex-wrap: wrap;
	}

	.no-radio {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		color: #888;
	}

	.no-radio a { color: #4a9eff; }
</style>
