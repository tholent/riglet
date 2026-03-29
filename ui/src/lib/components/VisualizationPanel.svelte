<script lang="ts">
	import { onMount } from 'svelte';
	import LufsMeter from '$lib/components/LufsMeter.svelte';
	import type { VisualizationMode } from '$lib/viz/types.js';
	import type { Renderer, RendererContext, VisualizationData } from '$lib/viz/types.js';
	import { createRenderer } from '$lib/viz/base-renderer.js';
	import { WaterfallRenderer } from '$lib/viz/waterfall-renderer.js';
	import { SpectrumRenderer } from '$lib/viz/spectrum-renderer.js';
	import { OscilloscopeRenderer } from '$lib/viz/oscilloscope-renderer.js';
	import { ConstellationRenderer } from '$lib/viz/constellation-renderer.js';
	import { PhaseRenderer } from '$lib/viz/phase-renderer.js';
	import { Spectrogram3dRenderer } from '$lib/viz/spectrogram3d-renderer.js';

	void WaterfallRenderer;
	void SpectrumRenderer;
	void OscilloscopeRenderer;
	void ConstellationRenderer;
	void PhaseRenderer;
	void Spectrogram3dRenderer;

	interface Props {
		mode: VisualizationMode;
		radioId: string;
		pcmSamples?: Float32Array | null;
		/** External FFT bins (e.g. from client-side mic FFT in simulation mode). When provided,
		 *  fed to renderers instead of waiting for the waterfall WebSocket. */
		fftBins?: Float32Array | null;
		sampleRate?: number;
		cursorMhz?: number;
		radioMode?: string;
	}

	let {
		mode = $bindable('waterfall' as VisualizationMode),
		radioId,
		pcmSamples = null,
		fftBins = null,
		sampleRate = 16000,
		cursorMhz = 0,
		radioMode = '',
	}: Props = $props();

	// ---------------------------------------------------------------------------
	// Waterfall controls (speed, dB floor/ceiling)
	// ---------------------------------------------------------------------------
	const WF_SPEED_KEY = 'riglet:wfSpeed';
	const WF_FLOOR_KEY = 'riglet:wfFloor';
	const WF_CEIL_KEY = 'riglet:wfCeil';

	function loadNum(key: string, def: number): number {
		try { const v = Number(localStorage.getItem(key)); return isNaN(v) ? def : v; } catch { return def; }
	}

	let wfSpeed = $state(loadNum(WF_SPEED_KEY, 1));   // frames to skip per row
	let wfFloor = $state(loadNum(WF_FLOOR_KEY, -100)); // dB floor
	let wfCeil  = $state(loadNum(WF_CEIL_KEY, 0));     // dB ceiling
	let wfOpen  = $state(false);                        // controls popup open

	// Sync waterfall renderer whenever controls change
	$effect(() => {
		const speed = wfSpeed;
		const floor = wfFloor;
		const ceil  = wfCeil;
		if (renderer && 'setSpeed' in renderer) {
			(renderer as WaterfallRenderer).setSpeed(speed);
			(renderer as WaterfallRenderer).setRange(floor, ceil);
		}
		try {
			localStorage.setItem(WF_SPEED_KEY, String(speed));
			localStorage.setItem(WF_FLOOR_KEY, String(floor));
			localStorage.setItem(WF_CEIL_KEY, String(ceil));
		} catch { /* ignore */ }
	});

	// ---------------------------------------------------------------------------
	// LUFS position (left / right)
	// ---------------------------------------------------------------------------
	const LUFS_POSITION_KEY = 'riglet:lufsPosition';
	type LufsPosition = 'left' | 'right';

	function loadLufsPosition(): LufsPosition {
		try {
			const v = localStorage.getItem(LUFS_POSITION_KEY);
			return v === 'left' ? 'left' : 'right';
		} catch { return 'right'; }
	}

	let lufsPosition = $state<LufsPosition>(loadLufsPosition());

	function toggleLufsPosition() {
		lufsPosition = lufsPosition === 'right' ? 'left' : 'right';
		try { localStorage.setItem(LUFS_POSITION_KEY, lufsPosition); } catch { /* ignore */ }
	}

	// ---------------------------------------------------------------------------
	// Spectrum strip position (top / bottom)
	// ---------------------------------------------------------------------------
	const SPECTRUM_POSITION_KEY = 'riglet:spectrumPosition';
	type SpectrumPosition = 'top' | 'bottom';

	function loadSpectrumPosition(): SpectrumPosition {
		try {
			const v = localStorage.getItem(SPECTRUM_POSITION_KEY);
			return v === 'bottom' ? 'bottom' : 'top';
		} catch { return 'top'; }
	}

	let spectrumPosition = $state<SpectrumPosition>(loadSpectrumPosition());

	function toggleSpectrumPosition() {
		spectrumPosition = spectrumPosition === 'top' ? 'bottom' : 'top';
		try { localStorage.setItem(SPECTRUM_POSITION_KEY, spectrumPosition); } catch { /* ignore */ }
	}

	// ---------------------------------------------------------------------------
	// DOM refs
	// ---------------------------------------------------------------------------
	let canvas: HTMLCanvasElement;
	let wrapperEl: HTMLDivElement;
	let spectrumCanvas: HTMLCanvasElement;
	let spectrumStripEl: HTMLDivElement;

	// ---------------------------------------------------------------------------
	// Main renderer
	// ---------------------------------------------------------------------------
	let renderer: Renderer | null = null;
	let rendererContext: RendererContext | null = null;

	// ---------------------------------------------------------------------------
	// Spectrum strip renderer
	// ---------------------------------------------------------------------------
	let spectrumRenderer: SpectrumRenderer | null = null;
	let spectrumCtx: RendererContext | null = null;

	// Shared state from waterfall WS
	let centerMhz = 0;
	let spanKhz = 0;
	let ws: WebSocket | null = null;
	let ro: ResizeObserver | null = null;
	let spectrumRo: ResizeObserver | null = null;

	// -----------------------------------------------------------------------
	// WebSocket
	// -----------------------------------------------------------------------
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
					if (msg.center_mhz !== undefined && msg.center_mhz !== 0) centerMhz = msg.center_mhz;
					if (msg.span_khz !== undefined && msg.span_khz !== 0) spanKhz = msg.span_khz;

					if (renderer && rendererContext) {
						rendererContext.centerMhz = centerMhz;
						rendererContext.spanKhz = spanKhz;
						if ('updateFreq' in renderer && typeof renderer.updateFreq === 'function') {
							(renderer as WaterfallRenderer).updateFreq(centerMhz, spanKhz);
						}
					}
					feedFrame(msg.bins, null);
				}
			} catch { /* ignore */ }
		};

		ws.onclose = () => { setTimeout(connectWs, 3000); };
		ws.onerror = () => ws?.close();
	}

	// -----------------------------------------------------------------------
	// Main renderer lifecycle
	// -----------------------------------------------------------------------
	function buildContext(cvs: HTMLCanvasElement): RendererContext | null {
		const ctx2d = cvs.getContext('2d');
		if (!ctx2d) return null;
		return { canvas: cvs, ctx: ctx2d, width: cvs.width, height: cvs.height, centerMhz, spanKhz, mode: radioMode };
	}

	function mountRenderer(newMode: VisualizationMode): void {
		renderer?.destroy();
		renderer = null;
		const ctx = buildContext(canvas);
		if (!ctx) return;
		rendererContext = ctx;
		try {
			renderer = createRenderer(newMode);
			renderer.init(ctx);
			// Apply waterfall controls to freshly-created renderer
			if ('setSpeed' in renderer) {
				(renderer as WaterfallRenderer).setSpeed(wfSpeed);
				(renderer as WaterfallRenderer).setRange(wfFloor, wfCeil);
			}
		} catch (e) {
			console.warn('[VisualizationPanel] Failed to create renderer:', e);
		}
	}

	function mountSpectrumRenderer(): void {
		spectrumRenderer?.destroy();
		spectrumRenderer = null;
		const ctx = buildContext(spectrumCanvas);
		if (!ctx) return;
		spectrumCtx = ctx;
		spectrumRenderer = new SpectrumRenderer();
		spectrumRenderer.init(ctx);
	}

	function feedFrame(fftBins: number[] | null, pcm: Float32Array | null): void {
		if (renderer) {
			renderer.render({ fftBins, pcmSamples: pcm, sampleRate, timestamp: performance.now() } as VisualizationData);
		}
		if (spectrumRenderer && fftBins) {
			spectrumRenderer.render({ fftBins, pcmSamples: null, sampleRate, timestamp: performance.now() } as VisualizationData);
		}
	}

	// React to viz mode changes
	$effect(() => {
		const m = mode;
		if (renderer || rendererContext) mountRenderer(m);
	});

	// Forward external PCM to main renderer
	$effect(() => {
		const samples = pcmSamples;
		if (samples && renderer) feedFrame(null, samples);
	});

	// Forward external FFT bins (simulation mode: client-side mic FFT)
	$effect(() => {
		const bins = fftBins;
		if (!bins) return;
		const binsArr = Array.from(bins);
		if (renderer) renderer.render({ fftBins: binsArr, pcmSamples: null, sampleRate, timestamp: performance.now() } as VisualizationData);
		if (spectrumRenderer) spectrumRenderer.render({ fftBins: binsArr, pcmSamples: null, sampleRate, timestamp: performance.now() } as VisualizationData);
	});

	// Forward cursor to waterfall renderer
	$effect(() => {
		const freq = cursorMhz;
		const m = radioMode;
		if (renderer && 'updateCursor' in renderer && typeof renderer.updateCursor === 'function') {
			(renderer as WaterfallRenderer).updateCursor(freq, m);
		}
	});

	// -----------------------------------------------------------------------
	// Mount / unmount
	// -----------------------------------------------------------------------
	onMount(() => {
		// Main canvas
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
			if (rendererContext) { rendererContext.width = w; rendererContext.height = h; }
			renderer?.resize(w, h);
		});
		ro.observe(canvas);

		// Spectrum strip canvas
		spectrumCanvas.width = spectrumStripEl.clientWidth || 256;
		spectrumCanvas.height = spectrumStripEl.clientHeight || 80;
		mountSpectrumRenderer();

		spectrumRo = new ResizeObserver((entries) => {
			const entry = entries[0];
			if (!entry) return;
			const w = Math.round(entry.contentRect.width);
			const h = Math.round(entry.contentRect.height);
			if (w <= 0 || h <= 0) return;
			spectrumCanvas.width = w;
			spectrumCanvas.height = h;
			if (spectrumCtx) { spectrumCtx.width = w; spectrumCtx.height = h; }
			spectrumRenderer?.resize(w, h);
		});
		spectrumRo.observe(spectrumStripEl);

		connectWs();

		return () => {
			ro?.disconnect();
			spectrumRo?.disconnect();
			ws?.close();
			renderer?.destroy();
			spectrumRenderer?.destroy();
			renderer = null;
			spectrumRenderer = null;
		};
	});
</script>

<div class="viz-outer" role="img" aria-label="Visualization panel">
	{#if lufsPosition === 'left'}
		<div class="lufs-col lufs-left">
			<button class="lufs-toggle" onclick={toggleLufsPosition} title="Move LUFS meter to right" aria-label="Move LUFS meter to right">▶</button>
			<LufsMeter {pcmSamples} fillHeight />
		</div>
	{/if}

	<div class="viz-wrap" bind:this={wrapperEl}>
		<!-- Spectrum strip — always visible, position toggled top/bottom via CSS order -->
		<div
			class="spectrum-strip"
			class:spectrum-bottom={spectrumPosition === 'bottom'}
			bind:this={spectrumStripEl}
		>
			<canvas bind:this={spectrumCanvas} class="spectrum-canvas"></canvas>
			<button
				class="spectrum-toggle"
				onclick={toggleSpectrumPosition}
				title={spectrumPosition === 'top' ? 'Move spectrum to bottom' : 'Move spectrum to top'}
				aria-label={spectrumPosition === 'top' ? 'Move spectrum to bottom' : 'Move spectrum to top'}
			>{spectrumPosition === 'top' ? '▼' : '▲'}</button>
		</div>

		<!-- Main visualization canvas -->
		<canvas bind:this={canvas} class="viz-canvas"></canvas>

		<!-- Waterfall controls popup -->
		{#if mode === 'waterfall'}
		<div class="wf-popup-wrap">
			<button
				class="wf-toggle"
				class:wf-toggle-open={wfOpen}
				onclick={() => wfOpen = !wfOpen}
				title="Waterfall settings"
				aria-label="Waterfall settings"
			>⚙</button>
			{#if wfOpen}
			<div class="wf-controls">
				<div class="wf-controls-title">Waterfall</div>
				<label class="wf-label">
					<span>Speed</span>
					<input type="range" min="1" max="8" step="1" bind:value={wfSpeed} />
					<span class="wf-val">{wfSpeed}×</span>
				</label>
				<label class="wf-label">
					<span>Floor</span>
					<input type="range" min="-140" max="-10" step="5" bind:value={wfFloor} />
					<span class="wf-val">{wfFloor} dB</span>
				</label>
				<label class="wf-label">
					<span>Ceil</span>
					<input type="range" min="-80" max="0" step="5" bind:value={wfCeil} />
					<span class="wf-val">{wfCeil} dB</span>
				</label>
			</div>
			{/if}
		</div>
		{/if}
	</div>

	{#if lufsPosition === 'right'}
		<div class="lufs-col">
			<button class="lufs-toggle" onclick={toggleLufsPosition} title="Move LUFS meter to left" aria-label="Move LUFS meter to left">◀</button>
			<LufsMeter {pcmSamples} fillHeight />
		</div>
	{/if}
</div>

<style>
	.viz-outer {
		flex: 1;
		min-height: 0;
		display: flex;
		flex-direction: row;
		overflow: hidden;
		border: 1px solid #333;
		border-radius: 4px;
		background: #000;
	}

	/* ---- main canvas + spectrum strip column ---- */
	.viz-wrap {
		flex: 1;
		min-height: 0;
		overflow: hidden;
		display: flex;
		flex-direction: column;
		position: relative;
	}

	.viz-canvas {
		display: block;
		width: 100%;
		flex: 1;
		min-height: 0;
		image-rendering: pixelated;
	}

	/* ---- waterfall controls popup ---- */
	.wf-popup-wrap {
		position: absolute;
		top: 4px;
		right: 4px;
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 2px;
		z-index: 10;
	}

	.wf-toggle {
		background: rgba(0, 0, 0, 0.6);
		border: 1px solid #444;
		border-radius: 3px;
		color: #666;
		font-size: 0.75rem;
		line-height: 1;
		padding: 3px 5px;
		cursor: pointer;
	}
	.wf-toggle:hover { color: #ccc; border-color: #777; }
	.wf-toggle:focus-visible { outline: 1px solid #4a9eff; outline-offset: 2px; }
	.wf-toggle-open { color: #4a9eff; border-color: #4a9eff; }

	.wf-controls {
		display: flex;
		flex-direction: column;
		gap: 6px;
		background: rgba(10, 10, 10, 0.92);
		border: 1px solid #444;
		border-radius: 4px;
		padding: 8px 10px;
		pointer-events: auto;
	}

	.wf-controls-title {
		color: #666;
		font-size: 0.6rem;
		font-family: monospace;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		margin-bottom: 2px;
	}

	.wf-label {
		display: flex;
		align-items: center;
		gap: 6px;
		color: #888;
		font-size: 0.65rem;
		font-family: monospace;
		white-space: nowrap;
	}

	.wf-label span:first-child {
		width: 2.8em;
		text-align: right;
	}

	.wf-label input[type='range'] {
		width: 90px;
		accent-color: #4a9eff;
		cursor: pointer;
	}

	.wf-val {
		width: 4.5em;
		color: #bbb;
	}

	/* ---- spectrum strip ---- */
	.spectrum-strip {
		position: relative;
		flex: 0 0 28%;
		min-height: 60px;
		max-height: 160px;
		order: -1; /* top by default */
		border-bottom: 1px solid #2a2a2a;
		overflow: hidden;
	}

	.spectrum-strip.spectrum-bottom {
		order: 1; /* below main canvas */
		border-bottom: none;
		border-top: 1px solid #2a2a2a;
	}

	.spectrum-canvas {
		display: block;
		width: 100%;
		height: 100%;
		image-rendering: pixelated;
	}

	.spectrum-toggle {
		position: absolute;
		bottom: 3px;
		right: 3px;
		background: rgba(0, 0, 0, 0.55);
		border: 1px solid #444;
		border-radius: 3px;
		color: #777;
		font-size: 0.6rem;
		line-height: 1;
		padding: 2px 4px;
		cursor: pointer;
	}

	.spectrum-toggle:hover { color: #ccc; border-color: #777; }
	.spectrum-toggle:focus-visible { outline: 1px solid #4a9eff; outline-offset: 2px; }

	/* ---- LUFS sidebar ---- */
	.lufs-col {
		display: flex;
		flex-direction: column;
		align-items: center;
		width: 68px;
		background: #0d0d0d;
		border-left: 1px solid #222;
		padding: 4px 0;
		gap: 4px;
		flex-shrink: 0;
	}

	.lufs-left {
		border-left: none;
		border-right: 1px solid #222;
	}

	.lufs-toggle {
		background: none;
		border: none;
		color: #555;
		font-size: 0.6rem;
		cursor: pointer;
		padding: 2px;
		line-height: 1;
		flex-shrink: 0;
	}

	.lufs-toggle:hover { color: #aaa; }
	.lufs-toggle:focus-visible { outline: 1px solid #4a9eff; outline-offset: 2px; }
</style>
