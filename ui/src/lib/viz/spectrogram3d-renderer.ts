/**
 * Spectrogram3dRenderer — 3D perspective freq-time-amplitude waterfall.
 *
 * Renders a scrolling 3D spectrogram using the Canvas 2D API with a simple
 * oblique projection (isometric-style). Each incoming FFT frame is drawn as a
 * filled polyline at decreasing depth, creating a perspective view of the
 * spectrum over time.
 *
 * Registered in the RendererRegistry as 'spectrogram3d'.
 */

import { registerRenderer } from './base-renderer.js';
import type { Renderer, RendererContext, VisualizationData } from './types.js';

/** Maximum number of history frames to keep and render. */
const MAX_FRAMES = 48;

/** Oblique projection offsets per depth step (in CSS pixels). */
const DEPTH_DX = 2.5; // shift right per step back
const DEPTH_DY = 1.8; // shift up per step back

function binColor(amplitude: number, alpha: number): string {
	// amplitude is normalised 0..1
	const a = Math.max(0, Math.min(1, amplitude));
	if (a < 0.5) {
		const t = a * 2;
		return `rgba(${Math.round(t * 0)},${Math.round(50 + t * 180)},${Math.round(200 - t * 200)},${alpha})`;
	} else {
		const t = (a - 0.5) * 2;
		return `rgba(${Math.round(t * 255)},${Math.round(230 - t * 100)},0,${alpha})`;
	}
}

export class Spectrogram3dRenderer implements Renderer {
	private ctx: CanvasRenderingContext2D | null = null;
	private width = 0;
	private height = 0;

	/** Ring buffer of normalised FFT frames (newest at index 0). */
	private frames: Float32Array[] = [];

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
			const bins = data.fftBins;
			// Normalise to [0, 1] assuming input range of approximately -120..0 dB
			const norm = new Float32Array(bins.length);
			for (let i = 0; i < bins.length; i++) {
				norm[i] = Math.max(0, Math.min(1, (bins[i] + 120) / 120));
			}
			this.frames.unshift(norm);
			if (this.frames.length > MAX_FRAMES) {
				this.frames.length = MAX_FRAMES;
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

	// ------------------------------------------------------------------
	// Helpers
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

		if (this.frames.length === 0) return;

		const numFrames = this.frames.length;
		const bins = this.frames[0].length;

		// The most-recent frame is drawn at the front (largest y, no depth offset).
		// Each older frame is shifted up-right by DEPTH_DX/DEPTH_DY.
		const totalDepthX = DEPTH_DX * (numFrames - 1);
		const totalDepthY = DEPTH_DY * (numFrames - 1);

		// Front-frame baseline: bottom-centre of the drawable area
		const baselineY = h * 0.85 - totalDepthY;
		const plotLeft = 10;
		const plotRight = w - 10 - totalDepthX;
		const plotWidth = Math.max(1, plotRight - plotLeft);
		const plotHeight = (h - 20 - totalDepthY) * 0.7;

		// Draw oldest frames first so newer frames paint on top
		for (let fi = numFrames - 1; fi >= 0; fi--) {
			const frame = this.frames[fi];
			const depthX = DEPTH_DX * fi;
			const depthY = DEPTH_DY * fi;
			const alpha = 0.35 + 0.65 * (fi / Math.max(1, numFrames - 1));

			// Build a filled polygon for the frame
			const binCount = frame.length;
			const xStep = plotWidth / Math.max(1, binCount - 1);

			ctx.beginPath();
			// Start at bottom-left of this frame
			ctx.moveTo(plotLeft + depthX, baselineY + depthY);

			for (let bi = 0; bi < binCount; bi++) {
				const px = plotLeft + depthX + bi * xStep;
				const py = baselineY + depthY - frame[bi] * plotHeight;
				ctx.lineTo(px, py);
			}

			// Close back to baseline
			ctx.lineTo(plotLeft + depthX + (binCount - 1) * xStep, baselineY + depthY);
			ctx.closePath();

			// Fill with a gradient or solid colour based on the average amplitude
			const avg = frame.reduce((s, v) => s + v, 0) / Math.max(1, frame.length);
			ctx.fillStyle = binColor(avg, alpha * 0.6);
			ctx.fill();

			// Stroke the top edge with per-bin colour
			for (let bi = 0; bi < binCount - 1; bi++) {
				const x1 = plotLeft + depthX + bi * xStep;
				const y1 = baselineY + depthY - frame[bi] * plotHeight;
				const x2 = plotLeft + depthX + (bi + 1) * xStep;
				const y2 = baselineY + depthY - frame[bi + 1] * plotHeight;
				ctx.beginPath();
				ctx.moveTo(x1, y1);
				ctx.lineTo(x2, y2);
				ctx.strokeStyle = binColor((frame[bi] + frame[bi + 1]) / 2, alpha);
				ctx.lineWidth = 1;
				ctx.stroke();
			}
		}

		// Draw axis label
		ctx.fillStyle = 'rgba(150,150,150,0.6)';
		ctx.font = '10px monospace';
		ctx.textAlign = 'left';
		ctx.textBaseline = 'top';
		ctx.fillText('3D Spectrogram', 4, 4);
	}
}

// Register in the global RendererRegistry
registerRenderer('spectrogram3d', () => new Spectrogram3dRenderer());
