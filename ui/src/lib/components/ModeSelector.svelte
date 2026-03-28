<script lang="ts">
	import { onMount } from 'svelte';
	import type { ControlWebSocket } from '$lib/websocket.js';
	import { getRadioModes } from '$lib/api.js';

	interface Props {
		mode: string;
		controlWs: ControlWebSocket | null;
		radioId?: string;
	}
	let { mode, controlWs, radioId }: Props = $props();

	const FALLBACK_MODES = ['USB', 'LSB', 'AM', 'FM', 'CW', 'RTTY', 'FT8'];

	let modes = $state<string[]>(FALLBACK_MODES);
	// Cache per radioId: module-level so it persists across remounts
	const modeCache = new Map<string, string[]>();

	onMount(() => {
		if (!radioId) return;
		if (modeCache.has(radioId)) {
			modes = modeCache.get(radioId)!;
			return;
		}
		getRadioModes(radioId)
			.then((res) => {
				if (res.modes && res.modes.length > 0) {
					modes = res.modes;
					modeCache.set(radioId, res.modes);
				}
			})
			.catch(() => {
				// Fall back to generic list — already set
			});
	});

	function select(m: string) {
		controlWs?.send({ type: 'mode', mode: m });
	}

	function onModeKeydown(e: KeyboardEvent, m: string, index: number) {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			select(m);
		} else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
			e.preventDefault();
			const next = modes[index + 1];
			if (next) {
				const el = document.querySelector<HTMLButtonElement>(`[data-mode="${next}"]`);
				el?.focus();
			}
		} else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
			e.preventDefault();
			const prev = modes[index - 1];
			if (prev) {
				const el = document.querySelector<HTMLButtonElement>(`[data-mode="${prev}"]`);
				el?.focus();
			}
		}
	}
</script>

<div class="mode-selector" role="group" aria-label="Operating mode selector">
	{#each modes as m, i}
		<button
			class="mode-btn"
			class:active={mode === m}
			onclick={() => select(m)}
			onkeydown={(e) => onModeKeydown(e, m, i)}
			aria-label={`${m} mode`}
			aria-pressed={mode === m}
			data-mode={m}
		>
			{m}
		</button>
	{/each}
</div>

<style>
	.mode-selector {
		display: flex;
		gap: 4px;
		flex-wrap: wrap;
	}

	.mode-btn {
		padding: 4px 10px;
		border: 1px solid #444;
		border-radius: 4px;
		background: #1a1a1a;
		color: #aaa;
		font-size: 0.8rem;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.12s;
	}

	.mode-btn:hover:not(.active) {
		border-color: #666;
		color: #ccc;
	}

	.mode-btn.active {
		background: #4a9eff;
		border-color: #4a9eff;
		color: #fff;
	}

	.mode-btn:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
	}

	@media (prefers-reduced-motion: reduce) {
		.mode-btn {
			transition: none;
		}
	}
</style>
