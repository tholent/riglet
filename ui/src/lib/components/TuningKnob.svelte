<script lang="ts">
	import { untrack } from 'svelte';
	import type { ControlWebSocket } from '$lib/websocket.js';

	interface Props {
		freq: number;
		controlWs: ControlWebSocket | null;
	}
	let { freq, controlWs }: Props = $props();

	const STEP_OPTIONS = [10, 100, 1_000, 10_000, 100_000];
	let stepIdx = $state(2); // default 1 kHz
	let stepHz = $derived(STEP_OPTIONS[stepIdx]);

	function stepLabel(hz: number): string {
		return hz >= 1000 ? `${hz / 1000}k` : `${hz}`;
	}

	// Local frequency mirror — updated immediately on input so rapid dragging
	// accumulates correctly rather than stacking on a stale prop value.
	let localFreq = $state(untrack(() => freq));
	let isDragging = $state(false);
	$effect(() => { if (!isDragging) localFreq = freq; });

	// Accumulated fractional drag pixels
	let dragAccum = 0;
	let lastY = 0;
	const PIXELS_PER_STEP = 4;
	const DEG_PER_STEP = 5; // visual rotation per frequency step

	// Visual rotation accumulator
	let angleDeg = $state(0);

	function nudge(steps: number) {
		localFreq = Math.max(0.001, localFreq + (steps * stepHz) / 1_000_000);
		controlWs?.send({ type: 'freq', freq: localFreq });
		angleDeg = ((angleDeg + steps * DEG_PER_STEP) % 360 + 360) % 360;
	}

	function onPointerDown(e: PointerEvent) {
		isDragging = true;
		dragAccum = 0;
		lastY = e.clientY;
		(e.currentTarget as SVGElement).setPointerCapture(e.pointerId);
	}
	function onPointerMove(e: PointerEvent) {
		if (!isDragging) return;
		dragAccum += lastY - e.clientY; // up = positive
		lastY = e.clientY;
		const steps = Math.trunc(dragAccum / PIXELS_PER_STEP);
		if (steps !== 0) {
			dragAccum -= steps * PIXELS_PER_STEP;
			nudge(steps);
		}
	}
	function onPointerUp() { isDragging = false; }

	function onWheel(e: WheelEvent) {
		e.preventDefault();
		nudge(e.deltaY < 0 ? 1 : -1);
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'ArrowUp' || e.key === 'ArrowRight') { e.preventDefault(); nudge(1); }
		else if (e.key === 'ArrowDown' || e.key === 'ArrowLeft') { e.preventDefault(); nudge(-1); }
		else if (e.key === 'PageUp') { e.preventDefault(); nudge(10); }
		else if (e.key === 'PageDown') { e.preventDefault(); nudge(-10); }
	}

	function cycleStep() {
		stepIdx = (stepIdx + 1) % STEP_OPTIONS.length;
	}

	// SVG geometry
	const SIZE = 130;
	const CX = SIZE / 2, CY = SIZE / 2;
	const R_BEZEL = 60;
	const R_BODY  = 52;
	const R_TICK_OUTER = 58;
	const R_TICK_INNER_MAJOR = 50;
	const R_TICK_INNER_MINOR = 54;
	const R_CAP = 18.75;

	const NUM_TICKS = 36;
	const ticks = Array.from({ length: NUM_TICKS }, (_, i) => i * (360 / NUM_TICKS));

	function toRad(deg: number) { return (deg * Math.PI) / 180; }
	function polarXY(deg: number, r: number) {
		const rad = toRad(deg);
		return { x: CX + r * Math.cos(rad), y: CY + r * Math.sin(rad) };
	}

	// Indicator dimple angle: 0° = 12 o'clock, clockwise; converted to SVG (3 o'clock = 0°)
	const R_DIMPLE = 37;
	let dimpleSvgDeg = $derived(angleDeg - 90);
	let dimplePos = $derived(polarXY(dimpleSvgDeg, R_DIMPLE));
</script>

<div class="tuning-wrap" role="presentation">
	<div class="tuning-title">VFO</div>
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<svg
		viewBox="0 0 {SIZE} {SIZE}"
		width={SIZE}
		height={SIZE}
		class="tuning-svg"
		class:dragging={isDragging}
		onpointerdown={onPointerDown}
		onpointermove={onPointerMove}
		onpointerup={onPointerUp}
		onpointercancel={onPointerUp}
		onwheel={onWheel}
		onkeydown={onKeydown}
		role="spinbutton"
		aria-valuenow={localFreq}
		aria-label="VFO tuning knob — drag or scroll to tune"
		tabindex="0"
	>
		<!-- Bezel -->
		<circle cx={CX} cy={CY} r={R_BEZEL} fill="#0f0f0f" stroke="#333" stroke-width="2" />

		<!-- Tick marks -->
		{#each ticks as deg, i}
			{@const isMajor = i % 9 === 0}
			{@const p1 = polarXY(deg, isMajor ? R_TICK_INNER_MAJOR : R_TICK_INNER_MINOR)}
			{@const p2 = polarXY(deg, R_TICK_OUTER)}
			<line
				x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
				stroke={isMajor ? '#555' : '#2d2d2d'}
				stroke-width={isMajor ? 1.5 : 0.8}
			/>
		{/each}

		<!-- Knob body -->
		<circle cx={CX} cy={CY} r={R_BODY} fill="#1a1a1a" stroke="#383838" stroke-width="1" />
		<!-- Inner highlight ring -->
		<circle cx={CX} cy={CY} r={R_BODY - 4} fill="none" stroke="#222" stroke-width="1" />

		<!-- Indicator dimple (orbits as knob rotates) -->
		<circle cx={dimplePos.x} cy={dimplePos.y} r="12" fill="#0d0d0d" stroke="#444" stroke-width="1" />

		<!-- Centre cap (click to cycle step) -->
		<circle cx={CX} cy={CY} r={R_CAP} fill="#111" stroke="#3a3a3a" stroke-width="1" style="cursor:pointer" role="button" tabindex="-1" aria-label="Cycle tuning step" onpointerdown={(e) => { e.stopPropagation(); cycleStep(); }} />
		<!-- Step label in centre -->
		<text
			x={CX} y={CY + 1}
			text-anchor="middle"
			dominant-baseline="middle"
			fill="#666"
			font-size="7"
			font-family="monospace"
			style="pointer-events:none"
		>{stepLabel(stepHz)}</text>
	</svg>
</div>

<style>
	.tuning-wrap {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 6px;
		padding: 6px 0;
	}
	.tuning-title {
		font-size: 0.6rem;
		color: #555;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		font-family: monospace;
	}
	.tuning-svg {
		cursor: ns-resize;
		user-select: none;
		touch-action: none;
		outline: none;
	}
	.tuning-svg:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 3px;
		border-radius: 50%;
	}
	.tuning-svg.dragging { cursor: grabbing; }

</style>
