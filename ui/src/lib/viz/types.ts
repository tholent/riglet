/**
 * Core types and interfaces for the pluggable visualization renderer system.
 *
 * All visualization modes implement the `Renderer` interface.
 * The `RendererRegistry` maps `VisualizationMode` keys to factory functions
 * so new renderers can be added without modifying the data pipeline.
 */

/** Known visualization modes.  New modes are added here and registered. */
export type VisualizationMode =
	| 'waterfall'
	| 'spectrum'
	| 'oscilloscope'
	| 'constellation'
	| 'phase'
	| 'spectrogram3d';

/**
 * Context passed to a renderer on `init()` and kept updated by
 * the `VisualizationPanel` host as it resizes or the radio state changes.
 */
export interface RendererContext {
	/** The backing canvas element. */
	canvas: HTMLCanvasElement;
	/** 2D rendering context (pre-obtained from the canvas). */
	ctx: CanvasRenderingContext2D;
	/** Current canvas logical width in CSS pixels. */
	width: number;
	/** Current canvas logical height in CSS pixels. */
	height: number;
	/** Centre frequency of the current display window, in MHz. */
	centerMhz: number;
	/** Span of the current display window, in kHz. */
	spanKhz: number;
	/** Active radio mode string (e.g. "USB", "FM", "CW"). */
	mode: string;
}

/**
 * Data bundle delivered to `Renderer.render()` on every frame.
 * Either or both of `fftBins` and `pcmSamples` may be null if
 * the corresponding data source is not active.
 */
export interface VisualizationData {
	/** FFT magnitude bins from the server waterfall WebSocket.
	 *  Values are in the range [-120, 0] dB (or raw floats from the server). */
	fftBins: number[] | null;
	/** Raw PCM samples from the audio pipeline (Float32, normalised -1..+1). */
	pcmSamples: Float32Array | null;
	/** Sample rate of pcmSamples (typically 16000 Hz). */
	sampleRate: number;
	/** Monotonic timestamp (performance.now()) of this frame. */
	timestamp: number;
}

/** Interface every visualization renderer must implement. */
export interface Renderer {
	/**
	 * Called once when the renderer is first attached to a canvas.
	 * Perform one-time setup (allocate ImageData, build colour maps, etc.).
	 */
	init(context: RendererContext): void;

	/**
	 * Called for every incoming data frame.
	 * Draw the updated visualization onto `context.canvas`.
	 */
	render(data: VisualizationData): void;

	/**
	 * Called whenever the canvas dimensions change.
	 * Reallocate any size-dependent buffers (e.g. ImageData).
	 */
	resize(width: number, height: number): void;

	/**
	 * Called when the renderer is being replaced or the component unmounts.
	 * Release any held resources (timers, workers, WebGL contexts, etc.).
	 */
	destroy(): void;
}

/** Factory function signature stored in the registry. */
export type RendererFactory = () => Renderer;
