/**
 * OscilloscopeRenderer — time-domain waveform display.
 *
 * Renders PCM samples as a classic oscilloscope trace with:
 * - Zero-crossing trigger to stabilise the display
 * - Horizontal centre line and vertical time-division graticule
 * - Green trace on dark background, theme-aware
 *
 * Falls back to a flat line when no PCM samples arrive.
 * FFT data is ignored by this renderer.
 *
 * Registered in the RendererRegistry as 'oscilloscope'.
 */

import { registerRenderer } from './base-renderer.js';
import type { Renderer, RendererContext, VisualizationData } from './types.js';

// Number of time divisions shown horizontally
const H_DIVS = 10;
// Number of amplitude divisions shown vertically
const V_DIVS = 8;
// How many samples to display per frame (one screen width)
const DISPLAY_SAMPLES = 512;

export class OscilloscopeRenderer implements Renderer {
	private ctx: CanvasRenderingContext2D | null = null;
	private width = 0;
	private height = 0;

	init(context: RendererContext): void {
		this.ctx = context.ctx;
		this.width = context.width;
		this.height = context.height;
	}

	render(data: VisualizationData): void {
		if (!this.ctx) return;

		if (!data.pcmSamples || data.pcmSamples.length === 0) {
			this._drawIdle();
			return;
		}

		const triggered = this._findTrigger(data.pcmSamples);
		this._drawFrame(data.pcmSamples, triggered);
	}

	resize(width: number, height: number): void {
		this.width = width;
		this.height = height;
	}

	destroy(): void {
		this.ctx = null;
	}

	// ------------------------------------------------------------------
	// Private helpers
	// ------------------------------------------------------------------

	/** Find a rising zero-crossing trigger point in the sample buffer.
	 *  Returns the start index for display, or 0 if none found. */
	private _findTrigger(samples: Float32Array): number {
		// Look for a rising zero crossing in the first half of the buffer
		const searchEnd = Math.min(samples.length - DISPLAY_SAMPLES, samples.length >> 1);
		for (let i = 1; i < searchEnd; i++) {
			if (samples[i - 1] < 0 && samples[i] >= 0) {
				return i;
			}
		}
		return 0;
	}

	/** Draw the waveform starting at `offset` in the samples array. */
	private _drawFrame(samples: Float32Array, offset: number): void {
		if (!this.ctx) return;
		const ctx = this.ctx;
		const w = this.width;
		const h = this.height;

		// Background
		ctx.fillStyle = '#050d05';
		ctx.fillRect(0, 0, w, h);

		this._drawGraticule(ctx, w, h);

		const count = Math.min(DISPLAY_SAMPLES, samples.length - offset);
		if (count < 2) return;

		const midY = h / 2;
		const scaleY = h / 2; // ±1 amplitude fills half the canvas height each way

		ctx.strokeStyle = '#00e600';
		ctx.lineWidth = 1.5;
		ctx.shadowColor = '#00cc00';
		ctx.shadowBlur = 2;

		ctx.beginPath();
		for (let i = 0; i < count; i++) {
			const x = (i / (count - 1)) * w;
			const sample = samples[offset + i];
			const y = midY - sample * scaleY * 0.8; // 0.8 so peaks don't clip edge
			if (i === 0) ctx.moveTo(x, y);
			else ctx.lineTo(x, y);
		}
		ctx.stroke();

		ctx.shadowBlur = 0;
	}

	/** Draw graticule (grid) lines. */
	private _drawGraticule(
		ctx: CanvasRenderingContext2D,
		w: number,
		h: number,
	): void {
		ctx.strokeStyle = '#0d200d';
		ctx.lineWidth = 1;

		// Vertical division lines
		for (let d = 0; d <= H_DIVS; d++) {
			const x = (d / H_DIVS) * w;
			ctx.beginPath();
			ctx.moveTo(x, 0);
			ctx.lineTo(x, h);
			ctx.stroke();
		}

		// Horizontal division lines
		for (let d = 0; d <= V_DIVS; d++) {
			const y = (d / V_DIVS) * h;
			ctx.beginPath();
			ctx.moveTo(0, y);
			ctx.lineTo(w, y);
			ctx.stroke();
		}

		// Centre horizontal line (slightly brighter)
		ctx.strokeStyle = '#1a3a1a';
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(0, h / 2);
		ctx.lineTo(w, h / 2);
		ctx.stroke();
	}

	/** Render a flat idle line when no signal is present. */
	private _drawIdle(): void {
		if (!this.ctx) return;
		const ctx = this.ctx;
		const w = this.width;
		const h = this.height;

		ctx.fillStyle = '#050d05';
		ctx.fillRect(0, 0, w, h);
		this._drawGraticule(ctx, w, h);

		// Flat centre trace
		ctx.strokeStyle = '#00e600';
		ctx.lineWidth = 1.5;
		ctx.beginPath();
		ctx.moveTo(0, h / 2);
		ctx.lineTo(w, h / 2);
		ctx.stroke();
	}
}

// Self-register
registerRenderer('oscilloscope', () => new OscilloscopeRenderer());
