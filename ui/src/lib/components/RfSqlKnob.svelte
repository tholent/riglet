<script lang="ts">
	import { untrack } from 'svelte';
	import type { ControlWebSocket } from '$lib/websocket.js';
	import Knob from './Knob.svelte';

	interface Props {
		rfGain: number;
		squelch: number;
		mode: string;
		controlWs: ControlWebSocket | null;
	}
	let { rfGain, squelch, mode, controlWs }: Props = $props();

	// Which knob is currently active
	let activeKnob: 'rf' | 'sql' = $state('rf');

	// Local copies so the knob reflects state immediately on change
	let localRf = $state(untrack(() => rfGain));
	let localSql = $state(untrack(() => squelch));

	// Sync local copies when props change from backend
	$effect(() => { localRf = rfGain; });
	$effect(() => { localSql = squelch; });

	// Auto-follow mode: FM/AM → squelch; SSB/CW/digital → RF gain
	const FM_AM_MODES = new Set(['FM', 'WFM', 'AM', 'AMS']);
	$effect(() => {
		if (FM_AM_MODES.has(mode)) {
			activeKnob = 'sql';
		} else {
			activeKnob = 'rf';
		}
	});

	let value = $derived(activeKnob === 'rf' ? localRf : localSql);
	let label = $derived(activeKnob === 'rf' ? 'RF Gain' : 'Squelch');
	let defaultValue = $derived(activeKnob === 'rf' ? 50 : 0);

	function onchange(v: number) {
		if (activeKnob === 'rf') {
			localRf = v;
			controlWs?.send({ type: 'rf_gain', level: v });
		} else {
			localSql = v;
			controlWs?.send({ type: 'squelch', level: v });
		}
	}

	function onclick() {
		activeKnob = activeKnob === 'rf' ? 'sql' : 'rf';
	}
</script>

<div class="rfsql-wrap" aria-label="RF Gain / Squelch control">
	<Knob
		{value}
		min={0}
		max={100}
		step={5}
		{label}
		size={72}
		{defaultValue}
		{onchange}
	/>
	<label class="toggle-switch" title="Toggle RF Gain / Squelch">
		<span class="toggle-label" class:active={activeKnob === 'rf'}>RF</span>
		<input type="checkbox" checked={activeKnob === 'sql'} onchange={onclick} />
		<span class="track"><span class="thumb"></span></span>
		<span class="toggle-label" class:active={activeKnob === 'sql'}>SQL</span>
	</label>
</div>

<style>
	.rfsql-wrap {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 4px;
	}

	.toggle-switch {
		display: flex;
		align-items: center;
		gap: 5px;
		cursor: pointer;
		user-select: none;
	}

	.toggle-switch input {
		display: none;
	}

	.toggle-label {
		font-size: 0.6rem;
		font-family: monospace;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: #555;
		transition: color 0.15s;
	}

	.toggle-label.active {
		color: #4af;
	}

	.track {
		position: relative;
		width: 26px;
		height: 13px;
		background: #333;
		border-radius: 7px;
		border: 1px solid #555;
		display: flex;
		align-items: center;
		transition: background 0.15s;
	}

	input:checked ~ .track {
		background: #1a3a4a;
		border-color: #4af;
	}

	.thumb {
		position: absolute;
		left: 2px;
		width: 9px;
		height: 9px;
		background: #888;
		border-radius: 50%;
		transition: left 0.15s, background 0.15s;
	}

	input:checked ~ .track .thumb {
		left: 13px;
		background: #4af;
	}
</style>
