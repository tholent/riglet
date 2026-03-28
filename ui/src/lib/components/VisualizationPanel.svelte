<script lang="ts">
	import { onMount } from 'svelte';
	import type { VisualizationMode } from '$lib/viz/types.js';
	import type { Renderer, RendererContext, VisualizationData } from '$lib/viz/types.js';
	import { createRenderer } from '$lib/viz/base-renderer.js';
	import { WaterfallRenderer } from '$lib/viz/waterfall-renderer.js';
	import { SpectrumRenderer } from '$lib/viz/spectrum-renderer.js';
	import { OscilloscopeRenderer } from '$lib/viz/oscilloscope-renderer.js';
	import { ConstellationRenderer } from '$lib/viz/constellation-renderer.js';
	import { PhaseRenderer } from '$lib/viz/phase-renderer.js';
	import { Spectrogram3dRenderer } from '$lib/viz/spectrogram3d-renderer.js';

	// Side-effect imports to ensure all renderers are registered before use.
	// The imports above already trigger self-registration via their module-level
	// registerRenderer() calls.  TypeScript needs the import to be used so we
	// reference the constructors in a comment.
	void WaterfallRenderer;
	void SpectrumRenderer;
	void OscilloscopeRenderer;
	void ConstellationRenderer;
	void PhaseRenderer;
	void Spectrogram3dRenderer;

	interface Props {
		/** Which visualization to display. */
		mode: VisualizationMode;
		/** Radio ID — used to connect the waterfall WebSocket. */
		radioId: string;
		/** Raw PCM samples forwarded from the audio pipeline (Float32, -1..+1). */
		pcmSamples?: Float32Array | null;
		/** PCM sample rate in Hz (default 16000). */
		sampleRate?: number;
		/** Current tuned frequency in MHz (for passband cursor). */
		cursorMhz?: number;
		/** Current radio mode (e.g. "USB", "LSB") for passband cursor. */
		radioMode?: string;
	}

	let {
		mode = $bindable('waterfall' as VisualizationMode),
		radioId,
		pcmSamples = null,
		sampleRate = 16000,
		cursorMhz = 0,
		radioMode = '',
	}: Props = $props();

	let canvas: HTMLCanvasElement;
	let wrapperEl: HTMLDivElement;

	let renderer: Renderer | null = null;
	let rendererContext: RendererContext | null = null;
	let ws: WebSocket | null = null;
	let ro: ResizeObserver | null = null;

	// Freq state updated from WS messages; forwarded to renderer.
	let centerMhz = 0;
	let spanKhz = 0;

	// ---------------------------------------------------------------
	// WebSocket connection
	// ---------------------------------------------------------------

	function connectWs(): void {
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
					// Forward freq state to renderer (WaterfallRenderer has updateFreq)
					if (renderer && rendererContext) {
						rendererContext.centerMhz = centerMhz;
						rendererContext.spanKhz = spanKhz;
						if ('updateFreq' in renderer && typeof renderer.updateFreq === 'function') {
							(renderer as WaterfallRenderer).updateFreq(centerMhz, spanKhz);
						}
					}
					feedFrame(msg.bins, null);
				}
			} catch {
				// ignore parse errors
			}
		};

		ws.onclose = () => {
			setTimeout(connectWs, 3000);
		};
		ws.onerror = () => ws?.close();
	}

	// ---------------------------------------------------------------
	// Renderer lifecycle
	// ---------------------------------------------------------------

	function buildContext(): RendererContext | null {
		if (!canvas) return null;
		const ctx2d = canvas.getContext('2d');
		if (!ctx2d) return null;
		return {
			canvas,
			ctx: ctx2d,
			width: canvas.width,
			height: canvas.height,
			centerMhz,
			spanKhz,
			mode: radioMode,
		};
	}

	function mountRenderer(newMode: VisualizationMode): void {
		// Tear down previous renderer
		if (renderer) {
			renderer.destroy();
			renderer = null;
		}

		const ctx = buildContext();
		if (!ctx) return;
		rendererContext = ctx;

		try {
			renderer = createRenderer(newMode);
			renderer.init(ctx);
		} catch (e) {
			console.warn('[VisualizationPanel] Failed to create renderer:', e);
		}
	}

	function feedFrame(fftBins: number[] | null, pcm: Float32Array | null): void {
		if (!renderer) return;
		const data: VisualizationData = {
			fftBins,
			pcmSamples: pcm,
			sampleRate,
			timestamp: performance.now(),
		};
		renderer.render(data);
	}

	// React to mode changes at runtime
	$effect(() => {
		const m = mode;
		if (renderer || rendererContext) {
			mountRenderer(m);
		}
	});

	// Forward external PCM samples to the renderer
	$effect(() => {
		const samples = pcmSamples;
		if (samples && renderer) {
			feedFrame(null, samples);
		}
	});

	// Forward cursor (tuned freq + mode) to WaterfallRenderer when it changes
	$effect(() => {
		const freq = cursorMhz;
		const m = radioMode;
		if (renderer && 'updateCursor' in renderer && typeof renderer.updateCursor === 'function') {
			(renderer as WaterfallRenderer).updateCursor(freq, m);
		}
	});

	// ---------------------------------------------------------------
	// Mount / unmount
	// ---------------------------------------------------------------

	onMount(() => {
		const ctx2d = canvas.getContext('2d');
		if (!ctx2d) return;

		// Initial canvas size matches wrapper
		canvas.width = wrapperEl.clientWidth || 256;
		canvas.height = wrapperEl.clientHeight || 300;

		mountRenderer(mode);

		ro = new ResizeObserver((entries) => {
			const entry = entries[0];
			if (!entry) return;
			const w = Math.round(entry.contentRect.width);
			const h = Math.round(entry.contentRect.height);
			if (w <= 0 || h <= 0) return;

			canvas.width = w;
			canvas.height = h;

			if (rendererContext) {
				rendererContext.width = w;
				rendererContext.height = h;
			}
			renderer?.resize(w, h);
		});
		ro.observe(wrapperEl);

		connectWs();

		return () => {
			ro?.disconnect();
			ws?.close();
			renderer?.destroy();
			renderer = null;
		};
	});
</script>

<div class="viz-wrap" bind:this={wrapperEl} role="img" aria-label="Visualization panel">
	<canvas bind:this={canvas} class="viz-canvas"></canvas>
</div>

<style>
	.viz-wrap {
		flex: 1;
		min-height: 0;
		overflow: hidden;
		background: #000;
		border: 1px solid #333;
		border-radius: 4px;
		display: flex;
		flex-direction: column;
	}

	.viz-canvas {
		display: block;
		width: 100%;
		height: 100%;
		flex: 1;
		min-height: 0;
		image-rendering: pixelated;
	}
</style>
