<script lang="ts">
	import LufsMeter from './LufsMeter.svelte';
	import PttButton from './PttButton.svelte';
	import TxDspPanel from './TxDspPanel.svelte';
	import type { ControlWebSocket } from '$lib/websocket.js';
	import type { TxDspChain } from '$lib/audio/tx-dsp-chain.js';

	interface Props {
		ptt: boolean;
		controlWs: ControlWebSocket | null;
		txGain: number;
		txDspChain: TxDspChain | null;
		txPcm: Float32Array | null;
		onTxGainChange: (v: number) => void;
		onTxDspChange: (detail: Record<string, unknown>) => void;
	}
	let { ptt, controlWs, txGain, txDspChain, txPcm, onTxGainChange, onTxDspChange }: Props = $props();

	const LUFS_POSITION_KEY = 'riglet:pttLufsPosition';
	type LufsPosition = 'left' | 'right';

	function loadPosition(): LufsPosition {
		try {
			const v = localStorage.getItem(LUFS_POSITION_KEY);
			return v === 'left' ? 'left' : 'right';
		} catch { return 'right'; }
	}

	let lufsPosition = $state<LufsPosition>(loadPosition());

	function togglePosition() {
		lufsPosition = lufsPosition === 'right' ? 'left' : 'right';
		try { localStorage.setItem(LUFS_POSITION_KEY, lufsPosition); } catch { /* ignore */ }
	}
</script>

<div class="ptt-panel">
	{#if lufsPosition === 'left'}
		<div class="lufs-col lufs-left">
			<button
				class="lufs-toggle"
				onclick={togglePosition}
				title="Move LUFS meter to right"
				aria-label="Move LUFS meter to right"
			>▶</button>
			<LufsMeter pcmSamples={txPcm} fillHeight />
		</div>
	{/if}

	<div class="ptt-left">
		<PttButton {ptt} {controlWs} />
	</div>

	<div class="ptt-dsp">
		<TxDspPanel {txDspChain} {txGain} {onTxGainChange} on:change={(e) => onTxDspChange(e.detail)} />
	</div>

	{#if lufsPosition === 'right'}
		<div class="lufs-col">
			<button
				class="lufs-toggle"
				onclick={togglePosition}
				title="Move LUFS meter to left"
				aria-label="Move LUFS meter to left"
			>◀</button>
			<LufsMeter pcmSamples={txPcm} fillHeight />
		</div>
	{/if}
</div>

<style>
	.ptt-panel {
		display: flex;
		flex-direction: row;
		align-items: stretch;
		background: var(--er-panel-bg);
		border: 1px solid var(--er-ctrl-bg);
		box-sizing: border-box;
		width: 100%;
	}

	.ptt-left {
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 10px 12px;
		flex-shrink: 0;
		border-right: 1px solid var(--er-divider);
	}

	.ptt-dsp {
		flex: 1;
		min-width: 0;
		display: flex;
		align-items: stretch;
	}

	.lufs-col {
		display: flex;
		flex-direction: column;
		align-items: center;
		width: 68px;
		background: var(--er-panel-dark);
		border-left: 1px solid var(--er-divider);
		padding: 4px 0;
		gap: 4px;
		flex-shrink: 0;
	}

	.lufs-left {
		border-left: none;
		border-right: 1px solid var(--er-divider);
	}

	.lufs-toggle {
		background: none;
		border: none;
		color: var(--er-label);
		font-size: 0.6rem;
		cursor: pointer;
		padding: 2px;
		line-height: 1;
		flex-shrink: 0;
	}

	.lufs-toggle:hover { color: var(--er-ctrl-text); }
	.lufs-toggle:focus-visible { outline: 1px solid var(--er-accent); outline-offset: 2px; }
</style>
