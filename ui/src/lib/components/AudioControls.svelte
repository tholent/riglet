<script lang="ts">
	import { untrack } from 'svelte';
	import { postAudioVolume } from '$lib/api.js';
	import type { AudioManager } from '$lib/audio/audio-manager.js';
	import type { ControlWebSocket } from '$lib/websocket.js';
	import Knob from './Knob.svelte';
	import RfSqlKnob from './RfSqlKnob.svelte';
	import TuneButton from './TuneButton.svelte';

	interface Props {
		radioId: string;
		rxVolume: number;
		txGain: number;
		audioManager: AudioManager | null;
		rfGain?: number;
		squelch?: number;
		mode?: string;
		controlWs?: ControlWebSocket | null;
		ptt?: boolean;
		tuning?: boolean;
		tunerEnabled?: boolean;
		swr?: number;
	}
	let {
		radioId, rxVolume = 50, txGain = 50, audioManager,
		rfGain = 50, squelch = 0, mode = 'USB', controlWs = null,
		ptt = false, tuning = false, tunerEnabled = false, swr = 1.0,
	}: Props = $props();

	let localRx = $state(untrack(() => rxVolume));
	let muted = $state(false);

	$effect(() => { localRx = rxVolume; });

	let applyTimer: ReturnType<typeof setTimeout> | null = null;

	function applyDebounced() {
		if (applyTimer) clearTimeout(applyTimer);
		applyTimer = setTimeout(() => {
			postAudioVolume(radioId, localRx, txGain, 0).catch((e) => {
				console.error('Failed to save audio volume:', e);
			});
		}, 300);
	}

	function onRxChange(v: number) {
		localRx = v;
		audioManager?.setVolume(muted ? 0 : localRx / 100);
		applyDebounced();
	}

	function toggleMute() {
		muted = !muted;
		audioManager?.setVolume(muted ? 0 : localRx / 100);
	}
</script>

<div class="audio-controls" role="group" aria-label="Audio controls">
	<!-- Knob stack: AF Gain + RF/SQL -->
	<div class="knob-stack">
		<Knob
			value={localRx}
			min={0} max={100} step={5}
			label={muted ? 'MUTED' : 'AF Gain'}
			size={72}
			onchange={onRxChange}
			onclick={toggleMute}
		/>
		<RfSqlKnob {rfGain} {squelch} {mode} {controlWs} />
	</div>

	<!-- Tuner column: eurorack module style -->
	<TuneButton {ptt} {tuning} {tunerEnabled} {swr} {controlWs} />
</div>

<style>
	.audio-controls {
		display: flex;
		flex-direction: row;
		align-items: stretch;
		gap: 0;
	}

	.knob-stack {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8px;
		padding: 8px 10px;
	}
</style>
