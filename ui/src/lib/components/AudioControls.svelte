<script lang="ts">
	import { postAudioVolume } from '$lib/api.js';
	import type { AudioManager } from '$lib/audio/audio-manager.js';

	interface Props {
		radioId: string;
		rxVolume: number;
		txGain: number;
		audioManager: AudioManager | null;
	}
	let { radioId, rxVolume = 50, txGain = 50, audioManager }: Props = $props();

	let localRx = $state(0);
	let localTx = $state(0);
	let muted = $state(false);
	let saving = $state(false);

	// Sync local state when props change from outside
	$effect(() => { localRx = rxVolume; });
	$effect(() => { localTx = txGain; });

	async function save() {
		saving = true;
		try {
			await postAudioVolume(radioId, localRx, localTx, 0);
			audioManager?.setVolume(muted ? 0 : localRx / 100);
		} catch (e) {
			console.error('Failed to save audio volume:', e);
		} finally {
			saving = false;
		}
	}

	function toggleMute() {
		muted = !muted;
		audioManager?.setVolume(muted ? 0 : localRx / 100);
	}
</script>

<div class="audio-controls">
	<div class="row">
		<label>
			<span>RX Vol</span>
			<input
				type="range"
				min="0"
				max="100"
				bind:value={localRx}
				oninput={() => audioManager?.setVolume(muted ? 0 : localRx / 100)}
			/>
			<span class="val">{localRx}</span>
		</label>
		<button class="mute-btn" class:muted onclick={toggleMute} aria-label={muted ? 'Unmute' : 'Mute'}>
			{muted ? '🔇' : '🔊'}
		</button>
	</div>

	<div class="row">
		<label>
			<span>TX Gain</span>
			<input type="range" min="0" max="100" bind:value={localTx} />
			<span class="val">{localTx}</span>
		</label>
	</div>

	<button class="save-btn" onclick={save} disabled={saving}>
		{saving ? 'Saving...' : 'Apply'}
	</button>
</div>

<style>
	.audio-controls {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.row {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	label {
		display: flex;
		align-items: center;
		gap: 8px;
		flex: 1;
		font-size: 0.85rem;
		color: #aaa;
	}

	label span:first-child {
		min-width: 56px;
	}

	input[type="range"] {
		flex: 1;
		accent-color: #4a9eff;
	}

	.val {
		min-width: 28px;
		text-align: right;
		font-family: monospace;
		color: #ccc;
	}

	.mute-btn {
		background: none;
		border: 1px solid #444;
		border-radius: 4px;
		padding: 4px 8px;
		cursor: pointer;
		font-size: 1rem;
	}

	.mute-btn.muted {
		border-color: #f44336;
	}

	.save-btn {
		align-self: flex-end;
		padding: 5px 14px;
		background: #2a2a2a;
		border: 1px solid #555;
		border-radius: 4px;
		color: inherit;
		cursor: pointer;
		font-size: 0.85rem;
	}

	.save-btn:hover:not(:disabled) { background: #333; }
	.save-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
