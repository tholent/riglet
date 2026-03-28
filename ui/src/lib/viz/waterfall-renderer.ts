/**
 * WaterfallRenderer — scrolling heat-map display of FFT magnitude over time.
 *
 * Each incoming FFT frame becomes one new row at the top of the canvas;
 * older rows scroll downward.  A frequency axis is drawn in the bottom
 * AXIS_HEIGHT pixels of the canvas.
 *
 * Registered in the RendererRegistry as 'waterfall'.
 */

import { registerRenderer } from './base-renderer.js';
import type { Renderer, RendererContext, VisualizationData } from './types.js';
import { computePassband, drawPassbandOverlay } from './cursor.js';

const AXIS_HEIGHT = 28;
const BINS = 256;

/** Map a normalised magnitude value [0, 1] to an RGB triple. */
function binToRgb(v: number): [number, number, number] {
	const c = Math.max(0, Math.min(1, v));
	if (c < 0.5) {
		const t = c * 2;
		return [Math.round(t * 255), Math.round(t * 200), Math.round((1 - t) * 200)];
	} else {
		const t = (c - 0.5) * 2;
		return [255, Math.round((1 - t) * 200), 0];
	}
}

function pickTickIntervalMhz(spanKhzVal: number): number {
	if (spanKhzVal <= 10) return 0.001;
	if (spanKhzVal <= 50) return 0.005;
	if (spanKhzVal <= 200) return 0.025;
	if (spanKhzVal <= 500) return 0.05;
	return 0.1;
}

export class WaterfallRenderer implements Renderer {
	private ctx: CanvasRenderingContext2D | null = null;
	private imageData: ImageData | null = null;
	private width = 0;
	private waterfallHeight = 0;
	private centerMhz = 0;
	private spanKhz = 0;
	private radioMode = '';
	/** Tuned frequency in MHz; 0 means use centerMhz (cursor at centre). */
	private cursorMhz = 0;

	init(context: RendererContext): void {
		this.ctx = context.ctx;
		this.width = context.width;
		this.waterfallHeight = Math.max(1, context.height - AXIS_HEIGHT);
		this._allocImageData();
		this.centerMhz = context.centerMhz;
		this.spanKhz = context.spanKhz;
		this.radioMode = context.mode;
	}

	render(data: VisualizationData): void {
		if (!this.ctx || !this.imageData) return;
		if (!data.fftBins) return;

		this._scrollAndDraw(data.fftBins);
		this._drawAxis();
		this._drawCursor();
	}

	resize(width: number, height: number): void {
		this.width = width;
		this.waterfallHeight = Math.max(1, height - AXIS_HEIGHT);
		this._allocImageData();
	}

	/** Called by VisualizationPanel when freq metadata updates. */
	updateFreq(centerMhz: number, spanKhz: number): void {
		this.centerMhz = centerMhz;
		this.spanKhz = spanKhz;
	}

	destroy(): void {
		this.ctx = null;
		this.imageData = null;
	}

	// ------------------------------------------------------------------
	// Private helpers
	// ------------------------------------------------------------------

	private _allocImageData(): void {
		if (!this.ctx) return;
		const h = this.waterfallHeight;
		const w = BINS;
		this.imageData = this.ctx.createImageData(w, h);
		// Fill opaque black
		this.imageData.data.fill(0);
		for (let i = 3; i < this.imageData.data.length; i += 4) {
			this.imageData.data[i] = 255;
		}
	}

	private _scrollAndDraw(bins: number[]): void {
		if (!this.ctx || !this.imageData) return;
		const h = this.imageData.height;
		const data = this.imageData.data;
		// Shift existing rows down by one row
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
		this.ctx.putImageData(this.imageData, 0, 0);
	}

	/** Update the cursor/tuned frequency (call from VisualizationPanel on state changes). */
	updateCursor(cursorMhz: number, mode: string): void {
		this.cursorMhz = cursorMhz;
		this.radioMode = mode;
	}

	private _drawAxis(): void {
		if (!this.ctx) return;
		const ctx = this.ctx;
		const w = this.width;
		const axisY = this.waterfallHeight;

		ctx.clearRect(0, axisY, w, AXIS_HEIGHT);
		ctx.fillStyle = '#0d0d0d';
		ctx.fillRect(0, axisY, w, AXIS_HEIGHT);

		if (this.centerMhz === 0 || this.spanKhz === 0 || w === 0) return;

		const halfSpanMhz = this.spanKhz / 2000;
		const startMhz = this.centerMhz - halfSpanMhz;
		const endMhz = this.centerMhz + halfSpanMhz;
		const spanMhz = endMhz - startMhz;
		const tickInterval = pickTickIntervalMhz(this.spanKhz);
		const firstTick = Math.ceil(startMhz / tickInterval) * tickInterval;

		ctx.font = '10px monospace';
		ctx.textAlign = 'center';
		ctx.textBaseline = 'top';

		for (let tick = firstTick; tick <= endMhz + 1e-9; tick += tickInterval) {
			const x = ((tick - startMhz) / spanMhz) * w;

			ctx.strokeStyle = '#555';
			ctx.lineWidth = 1;
			ctx.beginPath();
			ctx.moveTo(x, axisY);
			ctx.lineTo(x, axisY + 4);
			ctx.stroke();

			ctx.fillStyle = '#888';
			ctx.fillText(tick.toFixed(3), x, axisY + 6);
		}
	}

	private _drawCursor(): void {
		if (!this.ctx) return;
		// Need a valid frequency window and a mode to compute passband
		if (this.centerMhz === 0 || this.spanKhz === 0 || this.width === 0) return;
		// If cursorMhz is not yet set, nothing to draw
		if (this.cursorMhz === 0 && this.radioMode === '') return;

		const cursorFreq = this.cursorMhz !== 0 ? this.cursorMhz : this.centerMhz;
		if (cursorFreq === 0) return;

		const region = computePassband(
			this.centerMhz,
			this.spanKhz,
			cursorFreq,
			this.radioMode || 'USB',
			this.width,
		);

		drawPassbandOverlay(this.ctx, this.width, this.waterfallHeight, region);
	}
}

// Self-register
registerRenderer('waterfall', () => new WaterfallRenderer());
