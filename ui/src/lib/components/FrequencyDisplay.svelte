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
		<button
			class="nudge"
			onclick={() => nudge(-1)}
			aria-label="Tune down 1 kHz"
		>−</button>

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
				aria-label={`Frequency ${formatFreq(freq)} MHz. Press Enter to edit, arrow keys to nudge.`}
				aria-live="polite"
				aria-atomic="true"
			>
				{formatFreq(freq)}<span class="unit"> MHz</span>
			</button>
		{/if}

		<button
			class="nudge"
			onclick={() => nudge(1)}
			aria-label="Tune up 1 kHz"
		>+</button>
	</div>

	{#if activePreset}
		<span class="preset-label" aria-label={`Active preset: ${activePreset.name}`}>
			{activePreset.name}
		</span>
	{/if}
</div>

<style>
	.freq-wrap {
		display: inline-flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 2px;
	}

	.freq-row {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}

	.freq-display {
		font-size: 3.5rem;
		font-family: 'Courier New', monospace;
		font-weight: 700;
		color: #4cff8a;
		background: #0a0a0a;
		border: 1px solid #333;
		border-radius: 4px;
		padding: 4px 12px;
		cursor: pointer;
		letter-spacing: 0.02em;
		white-space: nowrap;
		line-height: 1;
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
		font-size: 3.5rem;
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

	.nudge {
		font-size: 1.4rem;
		width: 36px;
		height: 36px;
		background: #1a1a1a;
		border: 1px solid #444;
		border-radius: 4px;
		color: #ccc;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0;
		flex-shrink: 0;
	}

	.nudge:hover { background: #2a2a2a; border-color: #666; }

	.nudge:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
	}

	.preset-label {
		font-size: 0.78rem;
		color: var(--color-text-muted, #888);
		padding-left: 52px; /* align under the freq display (past the nudge button + gap) */
		font-style: italic;
	}

	@media (prefers-reduced-motion: reduce) {
		.nudge, .freq-display {
			transition: none;
		}
	}
</style>
