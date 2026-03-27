<script lang="ts">
	import { onMount } from 'svelte';

	interface Props {
		radioId: string;
	}
	let { radioId }: Props = $props();

	let canvas: HTMLCanvasElement;
	let ws: WebSocket | null = null;
	let animationFrame: number | null = null;

	// Waterfall image data — each row is one FFT frame (256 bins wide)
	const BINS = 256;
	const HEIGHT = 300;
	let imageData: ImageData | null = null;
	let ctx: CanvasRenderingContext2D | null = null;

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
		// Shift existing rows down by 1
		const data = imageData.data;
		data.copyWithin(BINS * 4, 0, BINS * (HEIGHT - 1) * 4);
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

	function connectWs() {
		const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
		const url = `${proto}//${location.host}/api/radio/${radioId}/ws/waterfall`;
		ws = new WebSocket(url);
		ws.onmessage = (event: MessageEvent) => {
			try {
				const msg = JSON.parse(event.data as string) as { type?: string; bins?: number[] };
				if (msg.type === 'fft' && Array.isArray(msg.bins)) {
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
		connectWs();

		return () => {
			ws?.close();
			if (animationFrame !== null) cancelAnimationFrame(animationFrame);
		};
	});
</script>

<div class="waterfall-wrap">
	<canvas
		bind:this={canvas}
		width={BINS}
		height={HEIGHT}
		class="waterfall-canvas"
	></canvas>
</div>

<style>
	.waterfall-wrap {
		width: 100%;
		overflow: hidden;
		background: #000;
		border: 1px solid #333;
		border-radius: 4px;
	}

	.waterfall-canvas {
		display: block;
		width: 100%;
		height: auto;
		image-rendering: pixelated;
	}
</style>
