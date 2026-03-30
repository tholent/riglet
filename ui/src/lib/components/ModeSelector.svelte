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

	/** Modes that are collapsed into the single 'DIG' button. */
	const DIGITAL_MODES = new Set(['RTTY', 'RTTYR', 'PKTUSB', 'PKTLSB']);
	/** Mode sent to the radio when DIG is selected. */
	const DIG_SEND_MODE = 'PKTUSB';

	const FALLBACK_MODES = ['USB', 'LSB', 'AM', 'FM', 'CW', 'DIG'];

	let displayModes = $state<string[]>(FALLBACK_MODES);
	const modeCache = new Map<string, string[]>();

	function processRawModes(raw: string[]): string[] {
		const filtered = raw.filter((m) => !DIGITAL_MODES.has(m));
		const hasDigital = raw.some((m) => DIGITAL_MODES.has(m));
		if (hasDigital) filtered.push('DIG');
		return filtered;
	}

	onMount(() => {
		if (!radioId) return;
		if (modeCache.has(radioId)) {
			displayModes = modeCache.get(radioId)!;
			return;
		}
		getRadioModes(radioId)
			.then((res) => {
				if (res.modes && res.modes.length > 0) {
					const processed = processRawModes(res.modes);
					displayModes = processed;
					modeCache.set(radioId, processed);
				}
			})
			.catch(() => { /* fall back to generic list */ });
	});

	function isActive(m: string): boolean {
		if (m === 'DIG') return DIGITAL_MODES.has(mode);
		return mode === m;
	}

	function select(m: string) {
		controlWs?.send({ type: 'mode', mode: m === 'DIG' ? DIG_SEND_MODE : m });
	}

	function onModeKeydown(e: KeyboardEvent, m: string, index: number) {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			select(m);
		} else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
			e.preventDefault();
			const next = displayModes[index + 1];
			if (next) document.querySelector<HTMLButtonElement>(`[data-mode="${next}"]`)?.focus();
		} else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
			e.preventDefault();
			const prev = displayModes[index - 1];
			if (prev) document.querySelector<HTMLButtonElement>(`[data-mode="${prev}"]`)?.focus();
		}
	}
</script>

<div class="mode-selector" role="group" aria-label="Operating mode selector">
	{#each displayModes as m, i (m)}
		<button
			class="mode-btn"
			class:active={isActive(m)}
			onclick={() => select(m)}
			onkeydown={(e) => onModeKeydown(e, m, i)}
			aria-label={m === 'DIG' ? 'Digital mode' : `${m} mode`}
			aria-pressed={isActive(m)}
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
		justify-content: center;
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
	.mode-btn:hover:not(.active) { border-color: #666; color: #ccc; }
	.mode-btn.active { background: #4a9eff; border-color: #4a9eff; color: #fff; }
	.mode-btn:focus-visible { outline: 2px solid #4a9eff; outline-offset: 2px; }
	@media (prefers-reduced-motion: reduce) { .mode-btn { transition: none; } }
</style>
