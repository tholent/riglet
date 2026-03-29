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

	// Layout constants (canvas pixels)
	const LABEL_W = 22; // width of each label column
	const BAR_W = 16;   // width of the level bar
	const CANVAS_W = LABEL_W * 2 + BAR_W; // 60px total

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
		if (t < 0.6) return '#4caf50';
		if (t < 0.85) return '#ffeb3b';
		return '#f44336';
	}

	function drawMeter(ctx: CanvasRenderingContext2D, w: number, h: number) {
		ctx.clearRect(0, 0, w, h);

		const barX = LABEL_W;

		// Outer background
		ctx.fillStyle = '#0d0d0d';
		ctx.fillRect(0, 0, w, h);

		// Bar track background
		ctx.fillStyle = '#1a1a1a';
		ctx.fillRect(barX, 0, BAR_W, h);

		// Level bar
		const levelT = lerp(currentLufs, MIN_LUFS, MAX_LUFS);
		const barH = Math.round(levelT * h);
		ctx.fillStyle = lufsToColor(currentLufs);
		ctx.fillRect(barX, h - barH, BAR_W, barH);

		// Peak-hold decay
		const now = performance.now();
		const timeSincePeak = now - peakHeldAt;
		if (timeSincePeak > PEAK_HOLD_MS) {
			const decayDb = ((timeSincePeak - PEAK_HOLD_MS) / 1000) * DECAY_DB_PER_SEC;
			peakLufs = Math.max(MIN_LUFS - 1, peakLufs - decayDb);
		}

		// Peak-hold line
		if (peakLufs > MIN_LUFS) {
			const peakT = lerp(peakLufs, MIN_LUFS, MAX_LUFS);
			const peakY = Math.round((1 - peakT) * h);
			ctx.fillStyle = '#fff';
			ctx.fillRect(barX, peakY, BAR_W, 2);
		}

		// Tick marks + labels
		const ticks = [-60, -40, -23, -18, -9, 0];
		const fontSize = Math.max(7, Math.min(9, Math.round(h / 28)));
		ctx.font = `${fontSize}px monospace`;
		ctx.textBaseline = 'middle';

		for (const tick of ticks) {
			const t = lerp(tick, MIN_LUFS, MAX_LUFS);
			const y = Math.round((1 - t) * h);

			// Tick line across bar only
			ctx.fillStyle = '#3a3a3a';
			ctx.fillRect(barX, y, BAR_W, 1);

			const label = String(tick);

			// Left label (right-aligned up to bar edge)
			ctx.fillStyle = '#777';
			ctx.textAlign = 'right';
			ctx.fillText(label, barX - 3, y);

			// Right label (left-aligned from bar edge)
			ctx.textAlign = 'left';
			ctx.fillText(label, barX + BAR_W + 3, y);
		}

		// Numeric readout — drawn at fixed position in bar so it never shifts
		const readout = currentLufs <= MIN_LUFS - 1 ? '–∞' : currentLufs.toFixed(1);
		// Use widest expected value to size the background consistently
		const refWidth = ctx.measureText('-60.0').width;
		const pad = 2;
		const readX = barX + BAR_W / 2;
		const readY = h - fontSize / 2 - pad;
		ctx.fillStyle = 'rgba(0,0,0,0.75)';
		ctx.fillRect(readX - refWidth / 2 - pad, readY - fontSize / 2 - pad, refWidth + pad * 2, fontSize + pad * 2);
		ctx.fillStyle = '#bbb';
		ctx.textAlign = 'center';
		ctx.textBaseline = 'middle';
		ctx.fillText(readout, readX, readY);
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

</script>

<div
	bind:this={containerEl}
	class="lufs-meter"
	class:fill-height={fillHeight}
	aria-label="Audio level meter"
	role="meter"
	aria-valuenow={Math.round(currentLufs)}
	aria-valuemin={MIN_LUFS}
	aria-valuemax={MAX_LUFS}
>
	<canvas
		bind:this={canvasEl}
		width={CANVAS_W}
		height={200}
		class="lufs-canvas"
		aria-hidden="true"
	></canvas>
</div>

<style>
	.lufs-meter {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 4px;
		width: 64px;
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
		width: 60px;
	}

	.lufs-canvas {
		width: 60px;
		height: 200px;
		display: block;
	}

</style>
