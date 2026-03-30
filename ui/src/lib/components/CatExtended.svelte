<script lang="ts">
	import type { ControlWebSocket } from '$lib/websocket.js';
	import VfoSelector from './VfoSelector.svelte';
	import CtcssSelector from './CtcssSelector.svelte';

	interface Props {
		vfo: string;
		swr: number;
		ctcssTone: number;
		ptt: boolean;
		controlWs: ControlWebSocket | null;
	}
	let { vfo, ctcssTone, controlWs }: Props = $props();
</script>

<div class="cat-extended" aria-label="Extended CAT controls">
	<VfoSelector {vfo} {controlWs} />
	<CtcssSelector tone={ctcssTone} {controlWs} />
</div>

<style>
	.cat-extended {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
</style>
