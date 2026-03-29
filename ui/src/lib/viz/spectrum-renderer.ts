/**
 * SpectrumRenderer — frequency-domain (spectrum scope) display.
 *
 * Draws FFT bins as a filled area chart: x = frequency bin, y = amplitude (dB).
 * Green line + fill on dark background, frequency axis at bottom, dB axis at left.
 * Includes a peak-hold trace that decays slowly over time.
 *
 * Registered in the RendererRegistry as 'spectrum'.
 */

import { registerRenderer } from './base-renderer.js';
import type { Renderer, RendererContext, VisualizationData } from './types.js';

// Layout constants — no axis labels, so margins are minimal
const MARGIN_LEFT = 4;
const MARGIN_BOTTOM = 4;
const MARGIN_RIGHT = 4;
const MARGIN_TOP = 4;

// Peak-hold: fraction of amplitude to decay per frame (~10 fps → ~1 s full decay)
const PEAK_DECAY_RATE = 0.015;

// dB display range
const DB_MIN = -120;
const DB_MAX = 0;

export class SpectrumRenderer implements Renderer {
	private ctx: CanvasRenderingContext2D | null = null;
	private width = 0;
	private height = 0;
	private peakHold: number[] = [];
	private lastTimestamp = 0;

	init(context: RendererContext): void {
		this.ctx = context.ctx;
		this.width = context.width;
		this.height = context.height;
		this.peakHold = [];
	}

	render(data: VisualizationData): void {
		if (!this.ctx || !data.fftBins || data.fftBins.length === 0) return;

		const bins = data.fftBins;
		const dt = data.timestamp - this.lastTimestamp;
		this.lastTimestamp = data.timestamp;

		// Initialise or resize peak-hold array
		if (this.peakHold.length !== bins.length) {
			this.peakHold = bins.map((v) => v);
		}

		// Decay and update peak hold
		const decay = PEAK_DECAY_RATE * (dt > 0 ? dt / 100 : 1);
		for (let i = 0; i < bins.length; i++) {
			if (bins[i] > this.peakHold[i]) {
				this.peakHold[i] = bins[i];
			} else {
				this.peakHold[i] = Math.max(0, this.peakHold[i] - decay);
			}
		}

		this._draw(bins);
	}

	resize(width: number, height: number): void {
		this.width = width;
		this.height = height;
	}

	destroy(): void {
		this.ctx = null;
		this.peakHold = [];
	}

	// ------------------------------------------------------------------
	// Private helpers
	// ------------------------------------------------------------------

	private _draw(bins: number[]): void {
		if (!this.ctx) return;
		const ctx = this.ctx;
		const w = this.width;
		const h = this.height;

		// Background
		ctx.fillStyle = '#0a0a0a';
		ctx.fillRect(0, 0, w, h);

		const plotW = w - MARGIN_LEFT - MARGIN_RIGHT;
		const plotH = h - MARGIN_BOTTOM - MARGIN_TOP;
		if (plotW <= 0 || plotH <= 0) return;

		const plotX = MARGIN_LEFT;
		const plotY = MARGIN_TOP;

		// Clip to plot area
		ctx.save();
		ctx.beginPath();
		ctx.rect(plotX, plotY, plotW, plotH);
		ctx.clip();

		const n = bins.length;

		/** Map a bin index to canvas x */
		const toX = (i: number): number => plotX + (i / (n - 1)) * plotW;

		/** Map a normalised amplitude [0,1] to canvas y (1 = top, 0 = bottom) */
		const toY = (v: number): number => {
			// Treat v as normalised; map to dB range
			// If values look like dB (< 0 typically) normalise them
			let db: number;
			if (v <= 1 && v >= 0) {
				// Normalised 0..1 — treat as linear amplitude, convert to dB
				db = v > 0 ? 20 * Math.log10(v) : DB_MIN;
			} else {
				db = v; // already dB
			}
			const clamped = Math.max(DB_MIN, Math.min(DB_MAX, db));
			const t = (clamped - DB_MIN) / (DB_MAX - DB_MIN);
			return plotY + plotH - t * plotH;
		};

		// Draw graticule (horizontal dB lines)
		ctx.strokeStyle = '#1a2a1a';
		ctx.lineWidth = 1;
		for (let db = DB_MIN; db <= DB_MAX; db += 20) {
			const y = toY(db);
			ctx.beginPath();
			ctx.moveTo(plotX, y);
			ctx.lineTo(plotX + plotW, y);
			ctx.stroke();
		}

		// Vertical grid lines (every 32 bins)
		for (let i = 0; i < n; i += 32) {
			const x = toX(i);
			ctx.beginPath();
			ctx.moveTo(x, plotY);
			ctx.lineTo(x, plotY + plotH);
			ctx.stroke();
		}

		// Peak-hold trace (dimmer green)
		ctx.strokeStyle = 'rgba(0,160,0,0.45)';
		ctx.lineWidth = 1;
		ctx.beginPath();
		for (let i = 0; i < this.peakHold.length; i++) {
			const x = toX(i);
			const y = toY(this.peakHold[i]);
			if (i === 0) ctx.moveTo(x, y);
			else ctx.lineTo(x, y);
		}
		ctx.stroke();

		// Filled area (main trace)
		const baseY = plotY + plotH;
		ctx.beginPath();
		ctx.moveTo(toX(0), baseY);
		for (let i = 0; i < n; i++) {
			ctx.lineTo(toX(i), toY(bins[i]));
		}
		ctx.lineTo(toX(n - 1), baseY);
		ctx.closePath();

		const grad = ctx.createLinearGradient(0, plotY, 0, plotY + plotH);
		grad.addColorStop(0, 'rgba(0,220,0,0.55)');
		grad.addColorStop(1, 'rgba(0,80,0,0.15)');
		ctx.fillStyle = grad;
		ctx.fill();

		// Line stroke on top of fill
		ctx.strokeStyle = '#00e600';
		ctx.lineWidth = 1.5;
		ctx.beginPath();
		for (let i = 0; i < n; i++) {
			const x = toX(i);
			const y = toY(bins[i]);
			if (i === 0) ctx.moveTo(x, y);
			else ctx.lineTo(x, y);
		}
		ctx.stroke();

		ctx.restore();
	}
}

// Self-register
registerRenderer('spectrum', () => new SpectrumRenderer());
