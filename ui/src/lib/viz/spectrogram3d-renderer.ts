/**
 * Spectrogram3dRenderer — 3D perspective freq-time-amplitude waterfall.
 *
 * Uses a one-point perspective projection with the vanishing point centered
 * horizontally and the horizon lifted to ~20% from the top, giving a
 * slightly top-down birds-eye view of the spectrum history.
 *
 * Newest frames are at the front (bottom); oldest recede toward the horizon.
 *
 * Registered in the RendererRegistry as 'spectrogram3d'.
 */

import { registerRenderer } from './base-renderer.js';
import type { Renderer, RendererContext, VisualizationData } from './types.js';

/** Maximum number of history frames to keep and render. */
const MAX_FRAMES = 60;

/** Horizon as a fraction of canvas height from the top (lower = more top-down). */
const HORIZON_FRAC = 0.20;

/** How far toward the horizon the oldest frame sits (0=front, 1=exactly at horizon). */
const DEPTH_FRAC = 0.88;

/** Convert a raw bin value (dBFS or normalised [0,1]) to [0,1] using the dB window. */
function normalizeBin(v: number, floorDb: number, ceilDb: number): number {
	const db = v < 0 ? v : v > 0 ? 20 * Math.log10(v) : -160;
	return Math.max(0, Math.min(1, (db - floorDb) / (ceilDb - floorDb)));
}

function binColor(amplitude: number, alpha: number): string {
	const a = Math.max(0, Math.min(1, amplitude));
	if (a < 0.5) {
		const t = a * 2;
		return `rgba(0,${Math.round(50 + t * 180)},${Math.round(200 - t * 200)},${alpha.toFixed(2)})`;
	} else {
		const t = (a - 0.5) * 2;
		return `rgba(${Math.round(t * 255)},${Math.round(230 - t * 100)},0,${alpha.toFixed(2)})`;
	}
}

export class Spectrogram3dRenderer implements Renderer {
	private ctx: CanvasRenderingContext2D | null = null;
	private width = 0;
	private height = 0;

	/** Ring buffer of normalised [0,1] FFT frames (index 0 = newest). */
	private frames: Float32Array[] = [];

	// Speed control
	private frameSkip = 1;
	private frameCount = 0;

	// dB window for color/amplitude mapping
	private floorDb = -100;
	private ceilDb = 0;

	init(context: RendererContext): void {
		this.ctx = context.ctx;
		this.width = context.width;
		this.height = context.height;
		this.frames = [];
		this._clear();
	}

	render(data: VisualizationData): void {
		if (!this.ctx) return;

		if (data.fftBins && data.fftBins.length > 0) {
			this.frameCount++;
			if (this.frameCount % this.frameSkip === 0) {
				const bins = data.fftBins;
				const norm = new Float32Array(bins.length);
				for (let i = 0; i < bins.length; i++) {
					norm[i] = normalizeBin(bins[i], this.floorDb, this.ceilDb);
				}
				this.frames.unshift(norm);
				if (this.frames.length > MAX_FRAMES) this.frames.length = MAX_FRAMES;
			}
		}

		this._drawScene();
	}

	resize(width: number, height: number): void {
		this.width = width;
		this.height = height;
		this._drawScene();
	}

	destroy(): void {
		this.ctx = null;
		this.frames = [];
	}

	/** Frames to skip between rendered rows (1 = fastest, 8 = slowest). */
	setSpeed(framesPerRow: number): void {
		this.frameSkip = Math.max(1, Math.round(framesPerRow));
	}

	/** dB window: energy below floorDb → black; at/above ceilDb → full color. */
	setRange(floorDb: number, ceilDb: number): void {
		this.floorDb = floorDb;
		this.ceilDb = Math.max(floorDb + 1, ceilDb);
		// Re-normalise all cached frames with the new window
		// (frames were stored pre-normalised; we'd need raw data to re-normalise accurately,
		// so just clear history — new frames will use the updated range)
		this.frames = [];
	}

	// ------------------------------------------------------------------
	// Private helpers
	// ------------------------------------------------------------------

	private _clear(): void {
		if (!this.ctx) return;
		this.ctx.fillStyle = '#000';
		this.ctx.fillRect(0, 0, this.width, this.height);
	}

	private _drawScene(): void {
		if (!this.ctx) return;
		const ctx = this.ctx;
		const w = this.width;
		const h = this.height;

		this._clear();

		// Corner label
		ctx.fillStyle = 'rgba(150,150,150,0.6)';
		ctx.font = '10px monospace';
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('3D Spectrogram', 4, 4);

		if (this.frames.length === 0) return;

		const numFrames = this.frames.length;

		// One-point perspective geometry
		const vanishX = w / 2;
		const vanishY = h * HORIZON_FRAC;
		const frontY = h - 4;
		const margin = 6;
		const frontLeft = margin;
		const frontRight = w - margin;

		// Maximum amplitude height for the front frame
		const maxAmpH = (frontY - vanishY) * 0.55;

		// Draw oldest frames first (painter's algorithm: back → front)
		for (let fi = numFrames - 1; fi >= 0; fi--) {
			const frame = this.frames[fi];
			const binCount = frame.length;

			// Depth fraction: 0 = newest/front, DEPTH_FRAC = oldest/back
			const d = (fi / Math.max(1, numFrames - 1)) * DEPTH_FRAC;

			// Perspective-projected edges for this frame
			const leftX  = frontLeft  + (vanishX - frontLeft)  * d;
			const rightX = frontRight + (vanishX - frontRight) * d;
			const baseY  = frontY     - (frontY  - vanishY)    * d;
			const ampH   = maxAmpH * (1 - d);

			// Newer frames are more opaque
			const alpha = 0.15 + 0.85 * (1 - fi / Math.max(1, numFrames - 1));

			const frameW = rightX - leftX;

			// Build filled polygon: baseline → spectrum trace → back to baseline
			ctx.beginPath();
			ctx.moveTo(leftX, baseY);

			for (let bi = 0; bi < binCount; bi++) {
				const px = leftX + (bi / Math.max(1, binCount - 1)) * frameW;
				const py = baseY - frame[bi] * ampH;
				ctx.lineTo(px, py);
			}

			ctx.lineTo(rightX, baseY);
			ctx.closePath();

			// Very subtle fill — just enough to give depth without creating an opaque wall
			// when many frames stack. Ridge stroke lines are the primary visual.
			const avg = frame.reduce((s, v) => s + v, 0) / Math.max(1, binCount);
			ctx.fillStyle = binColor(avg, alpha * 0.06);
			ctx.fill();

			// Per-bin color on the spectrum ridge
			for (let bi = 0; bi < binCount - 1; bi++) {
				const x1 = leftX + (bi       / Math.max(1, binCount - 1)) * frameW;
				const y1 = baseY - frame[bi]     * ampH;
				const x2 = leftX + ((bi + 1) / Math.max(1, binCount - 1)) * frameW;
				const y2 = baseY - frame[bi + 1] * ampH;
				ctx.beginPath();
				ctx.moveTo(x1, y1);
				ctx.lineTo(x2, y2);
				ctx.strokeStyle = binColor((frame[bi] + frame[bi + 1]) / 2, alpha);
				ctx.lineWidth = 1;
				ctx.stroke();
			}
		}
	}
}

// Register in the global RendererRegistry
registerRenderer('spectrogram3d', () => new Spectrogram3dRenderer());
