<script lang="ts">
	import type { VisualizationMode } from '$lib/viz/types.js';

	interface ModeOption {
		mode: VisualizationMode;
		label: string;
		title: string;
	}

	const MODES: ModeOption[] = [
		{ mode: 'waterfall', label: 'WF', title: 'Waterfall' },
		{ mode: 'spectrum', label: 'SP', title: 'Spectrum Scope' },
		{ mode: 'oscilloscope', label: 'OSC', title: 'Oscilloscope' },
		{ mode: 'constellation', label: 'CON', title: 'Constellation' },
		{ mode: 'phase', label: 'PH', title: 'Phase Meter' },
		{ mode: 'spectrogram3d', label: '3D', title: '3D Spectrogram' },
	];

	interface Props {
		mode: VisualizationMode;
		onselect?: (mode: VisualizationMode) => void;
	}

	let { mode = $bindable('waterfall' as VisualizationMode), onselect }: Props = $props();

	function select(m: VisualizationMode) {
		mode = m;
		onselect?.(m);
	}

	function onKeydown(e: KeyboardEvent, index: number) {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			select(MODES[index].mode);
		} else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
			e.preventDefault();
			const next = MODES[(index + 1) % MODES.length];
			document.querySelector<HTMLButtonElement>(`[data-viz="${next.mode}"]`)?.focus();
		} else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
			e.preventDefault();
			const prev = MODES[(index - 1 + MODES.length) % MODES.length];
			document.querySelector<HTMLButtonElement>(`[data-viz="${prev.mode}"]`)?.focus();
		}
	}
</script>

<div class="viz-switcher" role="group" aria-label="Visualization mode selector">
	{#each MODES as opt, i}
		<button
			class="viz-btn"
			class:active={mode === opt.mode}
			onclick={() => select(opt.mode)}
			onkeydown={(e) => onKeydown(e, i)}
			aria-label={opt.title}
			aria-pressed={mode === opt.mode}
			title={opt.title}
			data-viz={opt.mode}
		>
			{opt.label}
		</button>
	{/each}
</div>

<style>
	.viz-switcher {
		display: flex;
		flex-direction: row;
		gap: 3px;
		padding: 3px 4px;
		background: rgba(0, 0, 0, 0.6);
	}

	.viz-btn {
		padding: 2px 7px;
		border: 1px solid #444;
		border-radius: 3px;
		background: #1a1a1a;
		color: #888;
		font-size: 0.7rem;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.1s;
		letter-spacing: 0.04em;
	}

	.viz-btn:hover:not(.active) {
		border-color: #666;
		color: #ccc;
	}

	.viz-btn.active {
		border-color: #4a9eff;
		color: #4a9eff;
		background: rgba(74, 158, 255, 0.12);
	}

	.viz-btn:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
	}

	@media (prefers-reduced-motion: reduce) {
		.viz-btn {
			transition: none;
		}
	}
</style>
