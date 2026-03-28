/**
 * PhaseRenderer — autocorrelation (phase/correlation) meter.
 *
 * Computes the normalized autocorrelation of the incoming PCM signal at lag 0
 * and displays it as a horizontal bar ranging from -1 (out of phase) through
 * 0 (uncorrelated) to +1 (in phase).
 *
 * Color coding: green (near +1), yellow (near 0), red (near -1).
 *
 * Registered in the RendererRegistry as 'phase'.
 */

import { registerRenderer } from './base-renderer.js';
import type { Renderer, RendererContext, VisualizationData } from './types.js';

const LABEL_FONT = '11px monospace';

export class PhaseRenderer implements Renderer {
	private ctx: CanvasRenderingContext2D | null = null;
	private width = 0;
	private height = 0;
	private _correlation = 0;

	init(context: RendererContext): void {
		this.ctx = context.ctx;
		this.width = context.width;
		this.height = context.height;
		this._draw();
	}

	render(data: VisualizationData): void {
		const samples = data.pcmSamples;
		if (samples && samples.length > 1) {
			this._correlation = this._computeCorrelation(samples);
		}
		this._draw();
	}

	resize(width: number, height: number): void {
		this.width = width;
		this.height = height;
		this._draw();
	}

	destroy(): void {
		this.ctx = null;
	}

	// ------------------------------------------------------------------
	// Computation
	// ------------------------------------------------------------------

	/**
	 * Normalized autocorrelation:
	 *   r = sum(x[i] * x[i+1]) / sum(x[i]^2)
	 * Clamped to [-1, +1].
	 */
	private _computeCorrelation(samples: Float32Array): number {
		let sumXX = 0;
		let sumXY = 0;
		for (let i = 0; i < samples.length - 1; i++) {
			sumXX += samples[i] * samples[i];
			sumXY += samples[i] * samples[i + 1];
		}
		if (sumXX === 0) return 0;
		return Math.max(-1, Math.min(1, sumXY / sumXX));
	}

	// ------------------------------------------------------------------
	// Drawing
	// ------------------------------------------------------------------

	private _draw(): void {
		if (!this.ctx) return;
		const ctx = this.ctx;
		const w = this.width;
		const h = this.height;

		// Background
		ctx.fillStyle = '#111';
		ctx.fillRect(0, 0, w, h);

		const padding = 20;
		const meterTop = h * 0.35;
		const meterBottom = h * 0.65;
		const meterHeight = meterBottom - meterTop;
		const meterLeft = padding;
		const meterRight = w - padding;
		const meterWidth = meterRight - meterLeft;
		const cx = meterLeft + meterWidth / 2; // pixel at correlation = 0

		// Background track
		ctx.fillStyle = '#222';
		ctx.fillRect(meterLeft, meterTop, meterWidth, meterHeight);

		// Filled bar from centre to current correlation position
		const r = this._correlation;
		const barEndX = cx + r * (meterWidth / 2);
		const barLeft = Math.min(cx, barEndX);
		const barWidth = Math.abs(barEndX - cx);

		ctx.fillStyle = this._barColor(r);
		ctx.fillRect(barLeft, meterTop, barWidth, meterHeight);

		// Centre line
		ctx.strokeStyle = '#555';
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(cx, meterTop - 4);
		ctx.lineTo(cx, meterBottom + 4);
		ctx.stroke();

		// Needle line at current value
		ctx.strokeStyle = '#fff';
		ctx.lineWidth = 2;
		ctx.beginPath();
		ctx.moveTo(barEndX, meterTop - 6);
		ctx.lineTo(barEndX, meterBottom + 6);
		ctx.stroke();

		// Labels: -1, 0, +1
		ctx.fillStyle = '#888';
		ctx.font = LABEL_FONT;
		ctx.textAlign = 'center';
		ctx.textBaseline = 'top';
		ctx.fillText('-1', meterLeft, meterBottom + 6);
		ctx.fillText('0', cx, meterBottom + 6);
		ctx.fillText('+1', meterRight, meterBottom + 6);

		// Title
		ctx.fillStyle = '#aaa';
		ctx.font = '12px monospace';
		ctx.textAlign = 'center';
		ctx.textBaseline = 'alphabetic';
		ctx.fillText('Phase Correlation', w / 2, meterTop - 10);

		// Numeric readout
		ctx.fillStyle = this._barColor(r);
		ctx.font = 'bold 14px monospace';
		ctx.textAlign = 'center';
		ctx.textBaseline = 'top';
		ctx.fillText(r.toFixed(2), w / 2, meterBottom + 22);
	}

	private _barColor(r: number): string {
		// green = +1, yellow = 0, red = -1
		if (r >= 0) {
			const t = r; // 0..1
			const red = Math.round((1 - t) * 200);
			const green = Math.round(100 + t * 155);
			return `rgb(${red}, ${green}, 0)`;
		} else {
			const t = -r; // 0..1
			const green = Math.round((1 - t) * 200);
			return `rgb(${Math.round(180 + t * 75)}, ${green}, 0)`;
		}
	}
}

// Register in the global RendererRegistry
registerRenderer('phase', () => new PhaseRenderer());
