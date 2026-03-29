<script lang="ts">
	import { postAudioVolume } from '$lib/api.js';
	import type { AudioManager } from '$lib/audio/audio-manager.js';
	import Knob from './Knob.svelte';

	interface Props {
		radioId: string;
		rxVolume: number;
		txGain: number;
		audioManager: AudioManager | null;
	}
	let { radioId, rxVolume = 50, txGain = 50, audioManager }: Props = $props();

	let localRx = $state(rxVolume);
	let localTx = $state(txGain);
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
</div>

<style>
	.audio-controls {
		display: flex;
		gap: 16px;
		align-items: center;
	}
</style>
