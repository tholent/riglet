<script lang="ts">
	import { onMount } from 'svelte';

	interface Props {
		smeter: number; // 0–15: 0=no signal, 1–9=S1–S9, 10–15=S9+10–S9+60
		/** When true, canvas height tracks the parent element via ResizeObserver. */
		fillHeight?: boolean;
	}
	let { smeter = 0, fillHeight = false }: Props = $props();

	// Layout constants — matches LufsMeter
	const LABEL_W = 22;
	const BAR_W = 16;
	const CANVAS_W = LABEL_W * 2 + BAR_W; // 60px

	const MIN_S = 0;
	const MAX_S = 15;

	// Peak hold
	let peakS = $state(0);
	let peakHeldAt = $state(0);
	const PEAK_HOLD_MS = 1500;
	const PEAK_DECAY_PER_SEC = 1.5; // S-units per second

	let canvasEl: HTMLCanvasElement;
	let containerEl: HTMLDivElement;
	let animFrame: number;

	// Track peak whenever smeter rises
	$effect(() => {
		if (smeter > peakS) {
			peakS = smeter;
			peakHeldAt = performance.now();
		}
	});

	function sToY(s: number, h: number): number {
		const t = Math.max(0, Math.min(1, s / MAX_S));
		return Math.round((1 - t) * h);
	}

	function readingLabel(s: number): string {
		if (s >= 9) return `S9+${(s - 9) * 10}`;
		if (s > 0) return `S${s}`;
		return 'S0';
	}

	function drawMeter(ctx: CanvasRenderingContext2D, w: number, h: number) {
		ctx.clearRect(0, 0, w, h);

		const barX = LABEL_W;

		// Background
		ctx.fillStyle = '#0d0d0d';
		ctx.fillRect(0, 0, w, h);

		// Bar track
		ctx.fillStyle = '#1a1a1a';
		ctx.fillRect(barX, 0, BAR_W, h);

		// Level bar — three colour zones
		const level = Math.max(MIN_S, Math.min(MAX_S, smeter));

		if (level > 0) {
			// Green: S1–S5
			const greenTop = sToY(Math.min(level, 5), h);
			const greenBot = sToY(0, h);
			if (greenBot > greenTop) {
				ctx.fillStyle = '#4caf50';
				ctx.fillRect(barX, greenTop, BAR_W, greenBot - greenTop);
			}
		}
		if (level > 5) {
			// Orange: S6–S8
			const orangeTop = sToY(Math.min(level, 9), h);
			const orangeBot = sToY(5, h);
			if (orangeBot > orangeTop) {
				ctx.fillStyle = '#ff9800';
				ctx.fillRect(barX, orangeTop, BAR_W, orangeBot - orangeTop);
			}
		}
		if (level > 9) {
			// Red: S9+
			const redTop = sToY(level, h);
			const redBot = sToY(9, h);
			if (redBot > redTop) {
				ctx.fillStyle = '#f44336';
				ctx.fillRect(barX, redTop, BAR_W, redBot - redTop);
			}
		}

		// Peak-hold decay
		const now = performance.now();
		const elapsed = now - peakHeldAt;
		if (elapsed > PEAK_HOLD_MS) {
			const decay = ((elapsed - PEAK_HOLD_MS) / 1000) * PEAK_DECAY_PER_SEC;
			peakS = Math.max(0, peakS - decay);
		}

		// Peak line
		if (peakS > 0) {
			const peakY = sToY(peakS, h);
			ctx.fillStyle = '#fff';
			ctx.fillRect(barX, peakY, BAR_W, 2);
		}

		// Tick marks + labels
		const ticks = [0, 3, 6, 9, 10, 12, 15];
		const tickLabels = ['S0', 'S3', 'S6', 'S9', '+10', '+30', '+60'];
		const fontSize = Math.max(7, Math.min(9, Math.round(h / 28)));
		ctx.font = `${fontSize}px monospace`;
		ctx.textBaseline = 'middle';

		for (let i = 0; i < ticks.length; i++) {
			const y = sToY(ticks[i], h);
			ctx.fillStyle = '#3a3a3a';
			ctx.fillRect(barX, y, BAR_W, 1);

			const label = tickLabels[i];
			ctx.fillStyle = '#777';
			ctx.textAlign = 'right';
			ctx.fillText(label, barX - 3, y);
			ctx.textAlign = 'left';
			ctx.fillText(label, barX + BAR_W + 3, y);
		}

		// Numeric readout
		const readout = readingLabel(Math.round(smeter));
		const refWidth = ctx.measureText('S9+60').width;
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
	class="smeter"
	class:fill-height={fillHeight}
	role="meter"
	aria-label="Signal strength meter"
	aria-valuenow={Math.round(smeter)}
	aria-valuemin={MIN_S}
	aria-valuemax={MAX_S}
	aria-valuetext={readingLabel(Math.round(smeter))}
>
	<canvas
		bind:this={canvasEl}
		width={CANVAS_W}
		height={200}
		class="smeter-canvas"
		aria-hidden="true"
	></canvas>
</div>

<style>
	.smeter {
		display: flex;
		flex-direction: column;
		align-items: center;
		width: 64px;
	}

	.smeter.fill-height {
		height: 100%;
		flex: 1;
		min-height: 0;
	}

	.smeter.fill-height .smeter-canvas {
		flex: 1;
		min-height: 0;
		height: 100%;
		width: 60px;
	}

	.smeter-canvas {
		width: 60px;
		height: 200px;
		display: block;
	}
</style>
