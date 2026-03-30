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
		{onclick}
	/>
	<div class="toggle-hint">{activeKnob === 'rf' ? 'RF' : 'SQL'} · click to switch</div>
</div>

<style>
	.rfsql-wrap {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2px;
	}

	.toggle-hint {
		font-size: 0.55rem;
		color: #555;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		font-family: monospace;
		white-space: nowrap;
	}
</style>
