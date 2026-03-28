<script lang="ts">
	import { onMount } from 'svelte';

	interface Props {
		radioId: string;
	}
	let { radioId }: Props = $props();

	let canvas: HTMLCanvasElement;
	let axisCanvas: HTMLCanvasElement;
	let wrapperEl: HTMLDivElement;
	let ws: WebSocket | null = null;
	let animationFrame: number | null = null;

	// Waterfall image data — each row is one FFT frame (256 bins wide)
	const BINS = 256;
	const HEIGHT = 300;
	const AXIS_HEIGHT = 28;
	let imageData: ImageData | null = null;
	let ctx: CanvasRenderingContext2D | null = null;
	let axisCtx: CanvasRenderingContext2D | null = null;

	// Frequency axis state
	let centerMhz = $state(0);
	let spanKhz = $state(0);
	let axisWidth = $state(0);
	let canvasHeight = $state(HEIGHT);

	// Color map: 0.0 (quiet) -> blue, 0.5 -> yellow, 1.0 (strong) -> red
	function binToRgb(v: number): [number, number, number] {
		const c = Math.max(0, Math.min(1, v));
		if (c < 0.5) {
			// blue -> green -> yellow
			const t = c * 2;
			return [Math.round(t * 255), Math.round(t * 200), Math.round((1 - t) * 200)];
		} else {
			// yellow -> red
			const t = (c - 0.5) * 2;
			return [255, Math.round((1 - t) * 200), 0];
		}
	}

	function scrollAndDraw(bins: number[]) {
		if (!ctx || !imageData) return;
		const h = imageData.height;
		// Shift existing rows down by 1
		const data = imageData.data;
		data.copyWithin(BINS * 4, 0, BINS * (h - 1) * 4);
		// Write new row at top
		for (let x = 0; x < BINS; x++) {
			const val = bins[x] ?? 0;
			const [r, g, b] = binToRgb(val);
			const offset = x * 4;
			data[offset] = r;
			data[offset + 1] = g;
			data[offset + 2] = b;
			data[offset + 3] = 255;
		}
		ctx.putImageData(imageData, 0, 0);
	}

	function pickTickIntervalMhz(spanKhzVal: number): number {
		if (spanKhzVal <= 10)  return 0.001;   // 1 kHz
		if (spanKhzVal <= 50)  return 0.005;   // 5 kHz
		if (spanKhzVal <= 200) return 0.025;   // 25 kHz
		if (spanKhzVal <= 500) return 0.050;   // 50 kHz
		return 0.100;                           // 100 kHz
	}

	function drawAxis() {
		if (!axisCtx) return;
		const w = axisWidth;
		const h = AXIS_HEIGHT;

		axisCtx.clearRect(0, 0, w, h);

		if (centerMhz === 0 || spanKhz === 0 || w === 0) return;

		const halfSpanMhz = spanKhz / 2000;
		const startMhz = centerMhz - halfSpanMhz;
		const endMhz   = centerMhz + halfSpanMhz;
		const spanMhz  = endMhz - startMhz;

		const tickIntervalMhz = pickTickIntervalMhz(spanKhz);

		// First tick at or after startMhz
		const firstTick = Math.ceil(startMhz / tickIntervalMhz) * tickIntervalMhz;

		axisCtx.font = '10px monospace';
		axisCtx.textAlign = 'center';
		axisCtx.textBaseline = 'top';

		for (let tickMhz = firstTick; tickMhz <= endMhz + 1e-9; tickMhz += tickIntervalMhz) {
			const x = ((tickMhz - startMhz) / spanMhz) * w;

			// Tick mark
			axisCtx.strokeStyle = '#555';
			axisCtx.lineWidth = 1;
			axisCtx.beginPath();
			axisCtx.moveTo(x, 0);
			axisCtx.lineTo(x, 4);
			axisCtx.stroke();

			// Label — format as MHz to 3 decimal places
			const label = tickMhz.toFixed(3);
			axisCtx.fillStyle = '#888';
			axisCtx.fillText(label, x, 6);
		}
	}

	// Redraw axis whenever any of its inputs change
	$effect(() => {
		// Touch all three reactive values so effect re-runs when any changes
		void centerMhz;
		void spanKhz;
		void axisWidth;
		drawAxis();
	});

	function connectWs() {
		const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
		const url = `${proto}//${location.host}/api/radio/${radioId}/ws/waterfall`;
		ws = new WebSocket(url);
		ws.onmessage = (event: MessageEvent) => {
			try {
				const msg = JSON.parse(event.data as string) as {
					type?: string;
					bins?: number[];
					center_mhz?: number;
					span_khz?: number;
				};
				if (msg.type === 'fft' && Array.isArray(msg.bins)) {
					if (msg.center_mhz !== undefined && msg.center_mhz !== 0) {
						centerMhz = msg.center_mhz;
					}
					if (msg.span_khz !== undefined && msg.span_khz !== 0) {
						spanKhz = msg.span_khz;
					}
					scrollAndDraw(msg.bins);
				}
			} catch {
				// ignore
			}
		};
		ws.onclose = () => {
			setTimeout(connectWs, 3000);
		};
		ws.onerror = () => ws?.close();
	}

	onMount(() => {
		ctx = canvas.getContext('2d');
		if (ctx) {
			imageData = ctx.createImageData(BINS, HEIGHT);
			// Fill black
			imageData.data.fill(0);
			for (let i = 3; i < imageData.data.length; i += 4) imageData.data[i] = 255;
		}

		axisCtx = axisCanvas.getContext('2d');

		// Track wrapper size — width for axis labels, height for canvas resize
		const ro = new ResizeObserver((entries) => {
			const entry = entries[0];
			if (!entry) return;
			const w = Math.round(entry.contentRect.width);
			const h = Math.round(entry.contentRect.height) - AXIS_HEIGHT;
			if (axisCanvas.width !== w) axisCanvas.width = w;
			axisWidth = w;
			// Resize the waterfall canvas and recreate imageData when height changes
			if (h > 0 && h !== canvasHeight) {
				canvasHeight = h;
				canvas.height = h;
				if (ctx) {
					imageData = ctx.createImageData(BINS, h);
					imageData.data.fill(0);
					for (let i = 3; i < imageData.data.length; i += 4) imageData.data[i] = 255;
				}
			}
			drawAxis();
		});
		ro.observe(wrapperEl);

		connectWs();

		return () => {
			ro.disconnect();
			ws?.close();
			if (animationFrame !== null) cancelAnimationFrame(animationFrame);
		};
	});
</script>

<div class="waterfall-wrap" bind:this={wrapperEl}>
	<canvas
		bind:this={canvas}
		width={BINS}
		height={HEIGHT}
		class="waterfall-canvas"
	></canvas>
	<canvas
		bind:this={axisCanvas}
		width={0}
		height={AXIS_HEIGHT}
		class="axis-canvas"
	></canvas>
</div>

<style>
	.waterfall-wrap {
		flex: 1;
		min-height: 0;
		overflow: hidden;
		background: #000;
		border: 1px solid #333;
		border-radius: 4px;
		display: flex;
		flex-direction: column;
	}

	.waterfall-canvas {
		display: block;
		width: 100%;
		flex: 1;
		min-height: 0;
		image-rendering: pixelated;
	}

	.axis-canvas {
		display: block;
		width: 100%;
		height: 28px;
		background: #0d0d0d;
	}
</style>
