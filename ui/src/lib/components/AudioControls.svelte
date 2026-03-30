<script lang="ts">
	import { untrack } from 'svelte';
	import { postAudioVolume } from '$lib/api.js';
	import type { AudioManager } from '$lib/audio/audio-manager.js';
	import type { ControlWebSocket } from '$lib/websocket.js';
	import Knob from './Knob.svelte';
	import RfSqlKnob from './RfSqlKnob.svelte';

	interface Props {
		radioId: string;
		rxVolume: number;
		txGain: number;
		audioManager: AudioManager | null;
		rfGain?: number;
		squelch?: number;
		mode?: string;
		controlWs?: ControlWebSocket | null;
	}
	let { radioId, rxVolume = 50, txGain = 50, audioManager, rfGain = 50, squelch = 0, mode = 'USB', controlWs = null }: Props = $props();

	let localRx = $state(untrack(() => rxVolume));
	let localTx = $state(untrack(() => txGain));
	let muted = $state(false);

	$effect(() => { localRx = rxVolume; });
	$effect(() => { localTx = txGain; });

	let applyTimer: ReturnType<typeof setTimeout> | null = null;

	function applyDebounced() {
		if (applyTimer) clearTimeout(applyTimer);
		applyTimer = setTimeout(() => {
			postAudioVolume(radioId, localRx, localTx, 0).catch((e) => {
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

<style>
	.audio-controls {
		display: flex;
		flex-direction: column;
		gap: 8px;
		align-items: center;
	}
</style>
