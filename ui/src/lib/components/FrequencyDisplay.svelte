<script lang="ts">
	import type { ControlWebSocket } from '$lib/websocket.js';
	import type { PresetConfig } from '$lib/types.js';
	import { scrollWheel } from '$lib/actions/scrollwheel.js';

	interface Props {
		freq: number;
		controlWs: ControlWebSocket | null;
		/** Optional list of presets for showing an active-preset label. */
		presets?: PresetConfig[];
	}
	let { freq, controlWs, presets = [] }: Props = $props();

	let editing = $state(false);
	let editValue = $state('');

	// Format freq (MHz float) as XX.XXX.XXX with dot separators.
	// E.g. 14.2 -> "14.200.000", 7.03815 -> "7.038.150", 146.52 -> "146.520.000"
	function formatFreq(mhz: number): string {
		const hz = Math.round(mhz * 1_000_000);
		const sub   = hz % 1000;
		const khz   = Math.floor(hz / 1000) % 1000;
		const mhzPart = Math.floor(hz / 1_000_000);
		return `${mhzPart}.${String(khz).padStart(3, '0')}.${String(sub).padStart(3, '0')}`;
	}

	function startEdit() {
		editValue = freq.toFixed(6);
		editing = true;
	}

	function commitEdit() {
		const parsed = parseFloat(editValue);
		if (!isNaN(parsed) && parsed > 0) {
			controlWs?.send({ type: 'freq', freq: parsed });
		}
		editing = false;
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') commitEdit();
		if (e.key === 'Escape') editing = false;
	}

	function nudge(direction: 1 | -1) {
		controlWs?.send({ type: 'nudge', direction });
	}

	function onDisplayKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			startEdit();
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			nudge(1);
		} else if (e.key === 'ArrowDown') {
			e.preventDefault();
			nudge(-1);
		}
	}

	/** Find a preset within 1 kHz (0.001 MHz) of the current frequency. */
	const activePreset = $derived(
		presets.find((p) => Math.abs(p.frequency_mhz - freq) <= 0.001) ?? null,
	);
</script>

<div class="freq-wrap">
	<div
		class="freq-row"
		role="group"
		aria-label="Frequency control"
		use:scrollWheel={{ onDelta: (d) => nudge(d as 1 | -1) }}
	>
		{#if editing}
			<!-- svelte-ignore a11y_autofocus -->
			<input
				autofocus
				class="freq-input"
				type="text"
				bind:value={editValue}
				onblur={commitEdit}
				onkeydown={onKeydown}
				aria-label="Enter frequency in MHz"
			/>
		{:else}
			<button
				class="freq-display"
				onclick={startEdit}
				onkeydown={onDisplayKeydown}
				aria-label={`Frequency ${formatFreq(freq)} MHz${activePreset ? ` — ${activePreset.name}` : ''}. Press Enter to edit, arrow keys to nudge.`}
				aria-live="polite"
				aria-atomic="true"
			>
				<span class="freq-line">{formatFreq(freq)}<span class="unit"> MHz</span></span>
				<span class="preset-line" class:active={!!activePreset}>
					{activePreset?.name ?? '<none>'}
				</span>
			</button>
		{/if}

	</div>
</div>

<style>
	.freq-wrap {
		display: flex;
		flex-direction: column;
		align-items: center;
		width: 100%;
		gap: 2px;
	}

	.freq-row {
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.freq-display {
		display: flex;
		flex-direction: column;
		align-items: center;
		font-size: 4rem;
		font-family: 'Courier New', monospace;
		font-weight: 700;
		color: #4cff8a;
		background: #0a0a0a;
		border: 1px solid #333;
		border-radius: 4px;
		padding: 4px 12px 8px;
		cursor: pointer;
		letter-spacing: 0.02em;
		white-space: nowrap;
		line-height: 1;
	}

	.freq-line {
		display: block;
	}

	.preset-line {
		display: block;
		width: 100%;
		text-align: left;
		font-size: 1rem;
		font-weight: 400;
		color: #555;
		letter-spacing: 0.04em;
		margin-top: 4px;
		line-height: 1;
	}

	.preset-line.active {
		color: #4cff8a;
	}

	.freq-display:hover {
		border-color: #4a9eff;
	}

	.freq-display:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
	}

	.unit {
		font-size: 1rem;
		color: #888;
		font-weight: 400;
	}

	.freq-input {
		font-size: 4rem;
		font-family: 'Courier New', monospace;
		font-weight: 700;
		color: #4cff8a;
		background: #0a0a0a;
		border: 1px solid #4a9eff;
		border-radius: 4px;
		padding: 4px 12px;
		white-space: nowrap;
		line-height: 1;
		min-width: 260px;
	}

	@media (prefers-reduced-motion: reduce) {
		.freq-display {
			transition: none;
		}
	}
</style>
