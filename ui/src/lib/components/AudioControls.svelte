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

	function onRxKeydown(e: KeyboardEvent) {
		const step = 5;
		if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
			e.preventDefault();
			localRx = Math.min(100, localRx + step);
			audioManager?.setVolume(muted ? 0 : localRx / 100);
		} else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
			e.preventDefault();
			localRx = Math.max(0, localRx - step);
			audioManager?.setVolume(muted ? 0 : localRx / 100);
		} else if (e.key === 'Home') {
			e.preventDefault();
			localRx = 0;
			audioManager?.setVolume(0);
		} else if (e.key === 'End') {
			e.preventDefault();
			localRx = 100;
			audioManager?.setVolume(muted ? 0 : 1);
		}
	}

	function onTxKeydown(e: KeyboardEvent) {
		const step = 5;
		if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
			e.preventDefault();
			localTx = Math.min(100, localTx + step);
		} else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
			e.preventDefault();
			localTx = Math.max(0, localTx - step);
		} else if (e.key === 'Home') {
			e.preventDefault();
			localTx = 0;
		} else if (e.key === 'End') {
			e.preventDefault();
			localTx = 100;
		}
	}
</script>

<div class="audio-controls" role="group" aria-label="Audio controls">
	<div class="row">
		<label>
			<span>RX Vol</span>
			<input
				type="range"
				min="0"
				max="100"
				bind:value={localRx}
				oninput={() => audioManager?.setVolume(muted ? 0 : localRx / 100)}
				onkeydown={onRxKeydown}
				aria-label="Receive volume"
				aria-valuenow={localRx}
				aria-valuemin={0}
				aria-valuemax={100}
			/>
			<span class="val" aria-hidden="true">{localRx}</span>
		</label>
		<button
			class="mute-btn"
			class:muted
			onclick={toggleMute}
			aria-label={muted ? 'Unmute audio' : 'Mute audio'}
			aria-pressed={muted}
		>
			{muted ? '🔇' : '🔊'}
		</button>
	</div>

	<div class="row">
		<label>
			<span>TX Gain</span>
			<input
				type="range"
				min="0"
				max="100"
				bind:value={localTx}
				onkeydown={onTxKeydown}
				aria-label="Transmit gain"
				aria-valuenow={localTx}
				aria-valuemin={0}
				aria-valuemax={100}
			/>
			<span class="val" aria-hidden="true">{localTx}</span>
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

	input[type="range"]:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
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

	.mute-btn:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
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

	.save-btn:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
	}
</style>
