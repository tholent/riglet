/**
 * OscilloscopeRenderer — time-domain waveform display.
 *
 * Renders PCM samples as a classic oscilloscope trace with:
 * - Zero-crossing trigger to stabilise the display
 * - Horizontal centre line and vertical time-division graticule
 * - Green trace on dark background
 * - Time axis (ms) at the bottom
 *
 * Registered in the RendererRegistry as 'oscilloscope'.
 */

import { registerRenderer } from './base-renderer.js';
import type { Renderer, RendererContext, VisualizationData } from './types.js';

const H_DIVS = 10;
const V_DIVS = 8;
const DISPLAY_SAMPLES = 512;
const AXIS_HEIGHT = 20;

export class OscilloscopeRenderer implements Renderer {
	private ctx: CanvasRenderingContext2D | null = null;
	private width = 0;
	private height = 0;
	private sampleRate = 16000;

	init(context: RendererContext): void {
		this.ctx = context.ctx;
		this.width = context.width;
		this.height = context.height;
	}

	render(data: VisualizationData): void {
		if (!this.ctx) return;
		if (data.sampleRate) this.sampleRate = data.sampleRate;

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

	private _plotHeight(): number {
		return Math.max(1, this.height - AXIS_HEIGHT);
	}

	private _findTrigger(samples: Float32Array): number {
		const searchEnd = Math.min(samples.length - DISPLAY_SAMPLES, samples.length >> 1);
		for (let i = 1; i < searchEnd; i++) {
			if (samples[i - 1] < 0 && samples[i] >= 0) return i;
		}
		return 0;
	}

	private _drawFrame(samples: Float32Array, offset: number): void {
		if (!this.ctx) return;
		const ctx = this.ctx;
		const w = this.width;
		const ph = this._plotHeight();

		ctx.fillStyle = '#050d05';
		ctx.fillRect(0, 0, w, ph);
		this._drawGraticule(ctx, w, ph);

		const count = Math.min(DISPLAY_SAMPLES, samples.length - offset);
		if (count < 2) return;

		const midY = ph / 2;
		const scaleY = ph / 2;

		ctx.strokeStyle = '#00e600';
		ctx.lineWidth = 1.5;
		ctx.shadowColor = '#00cc00';
		ctx.shadowBlur = 2;
		ctx.beginPath();
		for (let i = 0; i < count; i++) {
			const x = (i / (count - 1)) * w;
			const y = midY - samples[offset + i] * scaleY * 0.8;
			if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
		}
		ctx.stroke();
		ctx.shadowBlur = 0;

		this._drawTimeAxis(ctx, w, ph);
		this._drawLabel(ctx);
	}

	private _drawIdle(): void {
		if (!this.ctx) return;
		const ctx = this.ctx;
		const w = this.width;
		const ph = this._plotHeight();

		ctx.fillStyle = '#050d05';
		ctx.fillRect(0, 0, w, ph);
		this._drawGraticule(ctx, w, ph);

		ctx.strokeStyle = '#00e600';
		ctx.lineWidth = 1.5;
		ctx.beginPath();
		ctx.moveTo(0, ph / 2);
		ctx.lineTo(w, ph / 2);
		ctx.stroke();

		this._drawTimeAxis(ctx, w, ph);
		this._drawLabel(ctx);
	}

	private _drawGraticule(ctx: CanvasRenderingContext2D, w: number, h: number): void {
		ctx.strokeStyle = '#0d200d';
		ctx.lineWidth = 1;

		for (let d = 0; d <= H_DIVS; d++) {
			const x = (d / H_DIVS) * w;
			ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
		}
		for (let d = 0; d <= V_DIVS; d++) {
			const y = (d / V_DIVS) * h;
			ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
		}

		ctx.strokeStyle = '#1a3a1a';
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(0, h / 2); ctx.lineTo(w, h / 2); ctx.stroke();
	}

	private _drawTimeAxis(ctx: CanvasRenderingContext2D, w: number, axisY: number): void {
		ctx.fillStyle = '#0d0d0d';
		ctx.fillRect(0, axisY, w, AXIS_HEIGHT);

		const totalMs = (DISPLAY_SAMPLES / this.sampleRate) * 1000;

		// Pick a round tick interval giving ~4-6 ticks
		const candidates = [1, 2, 5, 10, 20, 50];
		const tickMs = candidates.find((c) => totalMs / c <= 6) ?? candidates[candidates.length - 1];

		ctx.font = '9px monospace';
		ctx.textBaseline = 'top';

		for (let t = 0; t <= totalMs + 1e-9; t += tickMs) {
			const x = (t / totalMs) * w;
			// Tick mark
			ctx.fillStyle = '#444';
			ctx.fillRect(Math.round(x), axisY, 1, 4);
			// Label — left-align first tick, right-align last, center rest
			ctx.fillStyle = '#666';
			ctx.textAlign = t < 1e-9 ? 'left' : t >= totalMs - tickMs / 2 ? 'right' : 'center';
			ctx.fillText(`${Math.round(t)}ms`, x, axisY + 5);
		}
	}

	private _drawLabel(ctx: CanvasRenderingContext2D): void {
		ctx.fillStyle = 'rgba(150,150,150,0.6)';
		ctx.font = '10px monospace';
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('Oscilloscope', 4, 4);
	}
}

registerRenderer('oscilloscope', () => new OscilloscopeRenderer());
