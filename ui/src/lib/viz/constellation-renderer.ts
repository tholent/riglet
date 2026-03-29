/**
 * ConstellationRenderer — phase-space (X-Y) plot of audio signal.
 *
 * Plots successive PCM sample pairs as (sample[n], sample[n+1]) dots
 * on a circular display.  Dots fade over time via alpha blending to
 * produce a persistence / trail effect.
 *
 * Registered in the RendererRegistry as 'constellation'.
 */

import { registerRenderer } from './base-renderer.js';
import type { Renderer, RendererContext, VisualizationData } from './types.js';

const FADE_ALPHA = 0.06; // opacity of the fade overlay per frame
const DOT_RADIUS = 1.5;
const DOT_COLOR = 'rgba(0, 220, 80, 0.85)';
const GRATICULE_COLOR = 'rgba(80, 80, 80, 0.8)';

export class ConstellationRenderer implements Renderer {
	private ctx: CanvasRenderingContext2D | null = null;
	private width = 0;
	private height = 0;

	init(context: RendererContext): void {
		this.ctx = context.ctx;
		this.width = context.width;
		this.height = context.height;
		this._clear();
		this._drawGraticule();
	}

	render(data: VisualizationData): void {
		if (!this.ctx) return;
		const samples = data.pcmSamples;
		if (!samples || samples.length < 2) {
			// Fade toward black even with no data to show persistence decay
			this._fade();
			this._drawLabel();
			return;
		}

		this._fade();

		const ctx = this.ctx;
		const cx = this.width / 2;
		const cy = this.height / 2;
		const radius = Math.min(cx, cy) * 0.9;

		// Auto-gain: scale so the loudest sample fills ~90% of the radius.
		// Without this, quiet mic input (amplitudes ~0.01–0.05) clusters all
		// dots in a tiny region near the centre.
		let maxAbs = 0;
		for (let i = 0; i < samples.length; i++) {
			const a = Math.abs(samples[i]);
			if (a > maxAbs) maxAbs = a;
		}
		const gain = maxAbs > 0.001 ? 0.9 / maxAbs : 1;

		ctx.fillStyle = DOT_COLOR;
		ctx.beginPath();
		for (let i = 0; i < samples.length - 1; i++) {
			const x = cx + samples[i] * gain * radius;
			const y = cy - samples[i + 1] * gain * radius; // flip Y so +1 is up
			ctx.moveTo(x + DOT_RADIUS, y);
			ctx.arc(x, y, DOT_RADIUS, 0, Math.PI * 2);
		}
		ctx.fill();
		this._drawLabel();
	}

	resize(width: number, height: number): void {
		this.width = width;
		this.height = height;
		this._clear();
		this._drawGraticule();
	}

	destroy(): void {
		this.ctx = null;
	}

	// ------------------------------------------------------------------
	// Private helpers
	// ------------------------------------------------------------------

	private _clear(): void {
		if (!this.ctx) return;
		this.ctx.fillStyle = '#000';
		this.ctx.fillRect(0, 0, this.width, this.height);
	}

	private _fade(): void {
		if (!this.ctx) return;
		this.ctx.fillStyle = `rgba(0, 0, 0, ${FADE_ALPHA})`;
		this.ctx.fillRect(0, 0, this.width, this.height);
		// Redraw graticule on top of the fade so it stays visible
		this._drawGraticule();
	}

	private _drawLabel(): void {
		if (!this.ctx) return;
		this.ctx.fillStyle = 'rgba(150,150,150,0.6)';
		this.ctx.font = '10px monospace';
		this.ctx.textAlign = 'left';
		this.ctx.textBaseline = 'top';
		this.ctx.fillText('Constellation', 4, 4);
	}

	private _drawGraticule(): void {
		if (!this.ctx) return;
		const ctx = this.ctx;
		const cx = this.width / 2;
		const cy = this.height / 2;
		const radius = Math.min(cx, cy) * 0.9;

		ctx.save();
		ctx.strokeStyle = GRATICULE_COLOR;
		ctx.lineWidth = 1;

		// Horizontal crosshair
		ctx.beginPath();
		ctx.moveTo(cx - radius, cy);
		ctx.lineTo(cx + radius, cy);
		ctx.stroke();

		// Vertical crosshair
		ctx.beginPath();
		ctx.moveTo(cx, cy - radius);
		ctx.lineTo(cx, cy + radius);
		ctx.stroke();

		// Circular boundary
		ctx.beginPath();
		ctx.arc(cx, cy, radius, 0, Math.PI * 2);
		ctx.stroke();

		ctx.restore();
	}
}

// Register in the global RendererRegistry
registerRenderer('constellation', () => new ConstellationRenderer());
