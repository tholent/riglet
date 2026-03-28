/**
 * PassbandCursor — computes pixel positions for the receive passband region
 * given the current mode, centre frequency, and canvas dimensions.
 *
 * The cursor is drawn as a semi-transparent highlight over the passband,
 * with the area outside the passband dimmed.
 */

/** Mode bandwidth in kHz. */
export const MODE_BANDWIDTHS_KHZ: Record<string, number> = {
	USB: 2.4,
	LSB: 2.4,
	CW: 0.5,
	CWR: 0.5,
	AM: 6.0,
	FM: 12.0,
	WFM: 200.0,
	RTTY: 0.5,
	RTTYR: 0.5,
	PKTUSB: 2.4,
	PKTLSB: 2.4,
};

const DEFAULT_BANDWIDTH_KHZ = 3.0;

export interface PassbandRegion {
	/** Left edge of passband in canvas pixels. */
	leftPx: number;
	/** Right edge of passband in canvas pixels. */
	rightPx: number;
	/** Centre line (carrier) in canvas pixels. */
	centerPx: number;
}

/**
 * Compute the passband region in canvas pixel coordinates.
 *
 * @param centerMhz  Centre frequency of the waterfall display window (MHz).
 * @param spanKhz    Total span of the display window (kHz).
 * @param cursorMhz  The tuned/cursor frequency (MHz).
 * @param mode       Radio mode string (e.g. "USB", "LSB", "AM", "FM").
 * @param canvasWidth  Width of the canvas in pixels.
 */
export function computePassband(
	centerMhz: number,
	spanKhz: number,
	cursorMhz: number,
	mode: string,
	canvasWidth: number,
): PassbandRegion {
	const bwKhz = MODE_BANDWIDTHS_KHZ[mode.toUpperCase()] ?? DEFAULT_BANDWIDTH_KHZ;
	const halfSpanMhz = spanKhz / 2000;
	const startMhz = centerMhz - halfSpanMhz;
	const spanMhz = spanKhz / 1000;

	/** Convert a frequency in MHz to a canvas X pixel position. */
	function mhzToPx(mhz: number): number {
		if (spanMhz === 0) return canvasWidth / 2;
		return ((mhz - startMhz) / spanMhz) * canvasWidth;
	}

	const centerPx = mhzToPx(cursorMhz);
	const bwMhz = bwKhz / 1000;

	let leftPx: number;
	let rightPx: number;
	const modeUpper = mode.toUpperCase();

	if (modeUpper === 'USB' || modeUpper === 'PKTUSB') {
		// USB: passband extends ABOVE the carrier
		leftPx = centerPx;
		rightPx = mhzToPx(cursorMhz + bwMhz);
	} else if (modeUpper === 'LSB' || modeUpper === 'PKTLSB') {
		// LSB: passband extends BELOW the carrier
		leftPx = mhzToPx(cursorMhz - bwMhz);
		rightPx = centerPx;
	} else {
		// AM, FM, CW, RTTY, etc.: passband is centred
		leftPx = mhzToPx(cursorMhz - bwMhz / 2);
		rightPx = mhzToPx(cursorMhz + bwMhz / 2);
	}

	return { leftPx, rightPx, centerPx };
}

/**
 * Draw the passband overlay onto a 2D canvas context.
 *
 * Draws:
 *   - Semi-transparent blue tint over the passband
 *   - Dim overlay outside the passband
 *   - Thin vertical line at the cursor centre
 *
 * Call this AFTER the main renderer has drawn its content, so the overlay
 * appears on top.
 *
 * @param ctx          2D rendering context.
 * @param canvasWidth  Canvas width in pixels.
 * @param canvasHeight Canvas height to overlay (usually waterfallHeight, not including axis).
 * @param region       PassbandRegion from computePassband().
 */
export function drawPassbandOverlay(
	ctx: CanvasRenderingContext2D,
	canvasWidth: number,
	canvasHeight: number,
	region: PassbandRegion,
): void {
	const { leftPx, rightPx, centerPx } = region;

	// Dim the area outside the passband
	ctx.fillStyle = 'rgba(0, 0, 0, 0.35)';
	// Left of passband
	if (leftPx > 0) {
		ctx.fillRect(0, 0, Math.max(0, leftPx), canvasHeight);
	}
	// Right of passband
	if (rightPx < canvasWidth) {
		ctx.fillRect(Math.min(canvasWidth, rightPx), 0, canvasWidth - rightPx, canvasHeight);
	}

	// Semi-transparent blue highlight over passband
	const pbWidth = Math.max(1, rightPx - leftPx);
	ctx.fillStyle = 'rgba(74, 158, 255, 0.12)';
	ctx.fillRect(leftPx, 0, pbWidth, canvasHeight);

	// Thin passband edge lines
	ctx.strokeStyle = 'rgba(74, 158, 255, 0.5)';
	ctx.lineWidth = 1;
	if (leftPx !== centerPx) {
		ctx.beginPath();
		ctx.moveTo(leftPx, 0);
		ctx.lineTo(leftPx, canvasHeight);
		ctx.stroke();
	}
	if (rightPx !== centerPx) {
		ctx.beginPath();
		ctx.moveTo(rightPx, 0);
		ctx.lineTo(rightPx, canvasHeight);
		ctx.stroke();
	}

	// Centre/carrier line — bright white
	ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
	ctx.lineWidth = 1;
	ctx.beginPath();
	ctx.moveTo(centerPx, 0);
	ctx.lineTo(centerPx, canvasHeight);
	ctx.stroke();
}
