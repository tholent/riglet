<script lang="ts">
	import { LufsMeter } from '$lib/audio/lufs.js';
	import { onMount } from 'svelte';

	interface Props {
		pcmSamples: Float32Array | null;
		/** When true, canvas height tracks the parent element via ResizeObserver. */
		fillHeight?: boolean;
	}
	let { pcmSamples, fillHeight = false }: Props = $props();

	// LUFS meter instance (16 kHz sample rate to match the audio pipeline)
	const meter = new LufsMeter(16000);

	// Current momentary LUFS level
	let currentLufs = $state(-144);

	// Peak-hold: decays at 3 dB/sec
	let peakLufs = $state(-144);
	let peakHeldAt = $state(0); // timestamp when peak was set

	const MIN_LUFS = -60;
	const MAX_LUFS = 0;
	const DECAY_DB_PER_SEC = 3;
	const PEAK_HOLD_MS = 1500; // hold before decay starts

	let canvasEl: HTMLCanvasElement;
	let animFrame: number;

	// Feed new samples whenever pcmSamples changes
	$effect(() => {
		if (pcmSamples) {
			meter.process(pcmSamples);
			const lvl = meter.getMomentary();
			currentLufs = lvl;

			if (lvl > peakLufs) {
				peakLufs = lvl;
				peakHeldAt = performance.now();
			}
		}
	});

	function lerp(value: number, min: number, max: number): number {
		return Math.max(0, Math.min(1, (value - min) / (max - min)));
	}

	function lufsToColor(lufs: number): string {
		const t = lerp(lufs, MIN_LUFS, MAX_LUFS);
		if (t < 0.6) {
			// green
			return '#4caf50';
		} else if (t < 0.85) {
			// yellow
			return '#ffeb3b';
		} else {
			// red
			return '#f44336';
		}
	}

	function drawMeter(ctx: CanvasRenderingContext2D, w: number, h: number) {
		ctx.clearRect(0, 0, w, h);

		// Background track
		ctx.fillStyle = '#1a1a1a';
		ctx.fillRect(0, 0, w, h);

		// Level bar
		const levelT = lerp(currentLufs, MIN_LUFS, MAX_LUFS);
		const barH = Math.round(levelT * h);
		ctx.fillStyle = lufsToColor(currentLufs);
		ctx.fillRect(0, h - barH, w, barH);

		// Peak-hold line
		const now = performance.now();
		const timeSincePeak = now - peakHeldAt;

		if (timeSincePeak > PEAK_HOLD_MS) {
			// Decay
			const decayDb = ((timeSincePeak - PEAK_HOLD_MS) / 1000) * DECAY_DB_PER_SEC;
			peakLufs = Math.max(MIN_LUFS - 1, peakLufs - decayDb);
		}

		const peakT = lerp(peakLufs, MIN_LUFS, MAX_LUFS);
		if (peakLufs > MIN_LUFS) {
			const peakY = Math.round((1 - peakT) * h);
			ctx.fillStyle = '#fff';
			ctx.fillRect(0, peakY, w, 2);
		}

		// Tick marks at -60, -40, -23, -18, -9, 0
		const ticks = [-60, -40, -23, -18, -9, 0];
		ctx.fillStyle = '#555';
		ctx.font = '8px monospace';
		ctx.textAlign = 'right';
		for (const tick of ticks) {
			const t = lerp(tick, MIN_LUFS, MAX_LUFS);
			const y = Math.round((1 - t) * h);
			ctx.fillStyle = '#444';
			ctx.fillRect(0, y, w, 1);
		}
	}

	function animate() {
		if (!canvasEl) return;
		const ctx = canvasEl.getContext('2d');
		if (ctx) drawMeter(ctx, canvasEl.width, canvasEl.height);
		animFrame = requestAnimationFrame(animate);
	}

	let containerEl: HTMLDivElement;

	onMount(() => {
		animFrame = requestAnimationFrame(animate);

		let ro: ResizeObserver | null = null;
		if (fillHeight && containerEl) {
			ro = new ResizeObserver((entries) => {
				const h = Math.round(entries[0]?.contentRect.height ?? 0);
				if (h > 0 && canvasEl) canvasEl.height = h;
			});
			ro.observe(containerEl);
		}

		return () => {
			cancelAnimationFrame(animFrame);
			ro?.disconnect();
		};
	});

	// Numeric readout formatted to 1 decimal place
	const lufsLabel = $derived(
		currentLufs <= MIN_LUFS - 1 ? '–∞ LUFS' : `${currentLufs.toFixed(1)} LUFS`,
	);
</script>

<div
	bind:this={containerEl}
	class="lufs-meter"
	class:fill-height={fillHeight}
	aria-label={`Audio level: ${lufsLabel}`}
	role="meter"
	aria-valuenow={Math.round(currentLufs)}
	aria-valuemin={MIN_LUFS}
	aria-valuemax={MAX_LUFS}
>
	<canvas
		bind:this={canvasEl}
		width={32}
		height={200}
		class="lufs-canvas"
		aria-hidden="true"
	></canvas>
	<span class="lufs-label">{lufsLabel}</span>
</div>

<style>
	.lufs-meter {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 4px;
		width: 48px;
	}

	.lufs-meter.fill-height {
		height: 100%;
		flex: 1;
		min-height: 0;
	}

	.lufs-meter.fill-height .lufs-canvas {
		flex: 1;
		min-height: 0;
		height: 100%;
		width: 32px;
	}

	.lufs-canvas {
		width: 32px;
		height: 200px;
		border: 1px solid #333;
		border-radius: 2px;
		display: block;
	}

	.lufs-label {
		font-size: 0.62rem;
		font-family: 'Courier New', monospace;
		color: var(--color-text-muted, #888);
		text-align: center;
		white-space: nowrap;
	}
</style>
