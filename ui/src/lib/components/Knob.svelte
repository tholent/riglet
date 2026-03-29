<script lang="ts">
	interface Props {
		value: number;
		min?: number;
		max?: number;
		step?: number;
		label?: string;
		size?: number;
		onchange?: (v: number) => void;
		onclick?: () => void;
	}
	let { value, min = 0, max = 100, step = 1, label = '', size = 60, onchange, onclick }: Props = $props();

	let CX = $derived(size / 2);
	let CY = $derived(size / 2);
	let R = $derived(size * 0.37);
	// SVG arc: start 135° (7:30 position), sweep 270° clockwise to 45° (4:30)
	const START_DEG = 135;
	const SWEEP_DEG = 270;

	function toRad(deg: number) { return (deg * Math.PI) / 180; }

	function polarXY(deg: number, r: number) {
		return { x: CX + r * Math.cos(toRad(deg)), y: CY + r * Math.sin(toRad(deg)) };
	}

	function arcPath(startDeg: number, endDeg: number, sweepDeg: number, r: number): string {
		const s = polarXY(startDeg, r);
		const e = polarXY(endDeg, r);
		const largeArc = sweepDeg > 180 ? 1 : 0;
		return `M ${s.x.toFixed(2)} ${s.y.toFixed(2)} A ${r} ${r} 0 ${largeArc} 1 ${e.x.toFixed(2)} ${e.y.toFixed(2)}`;
	}

	let norm = $derived(Math.max(0, Math.min(1, (value - min) / (max - min))));
	let valueDeg = $derived(START_DEG + norm * SWEEP_DEG);
	let valueSweep = $derived(norm * SWEEP_DEG);
	let trackEndDeg = START_DEG + SWEEP_DEG; // 45°
	let dot = $derived(polarXY(valueDeg, R * 0.62));

	let dragging = $state(false);
	let dragMoved = false;
	let dragStartY = 0;
	let dragStartVal = 0;

	function clampStep(v: number) {
		return Math.max(min, Math.min(max, Math.round(v / step) * step));
	}

	function onPointerDown(e: PointerEvent) {
		dragging = true;
		dragMoved = false;
		dragStartY = e.clientY;
		dragStartVal = value;
		(e.currentTarget as SVGElement).setPointerCapture(e.pointerId);
	}
	function onPointerMove(e: PointerEvent) {
		if (!dragging) return;
		const dy = dragStartY - e.clientY;
		if (Math.abs(dy) > 3) dragMoved = true;
		const newVal = clampStep(dragStartVal + (dy / 80) * (max - min));
		if (newVal !== value) onchange?.(newVal);
	}
	function onPointerUp() {
		if (!dragMoved) onclick?.();
		dragging = false;
	}

	function onWheel(e: WheelEvent) {
		e.preventDefault();
		const newVal = clampStep(value + (e.deltaY < 0 ? step : -step));
		if (newVal !== value) onchange?.(newVal);
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'ArrowUp' || e.key === 'ArrowRight') {
			e.preventDefault();
			const newVal = clampStep(value + step);
			if (newVal !== value) onchange?.(newVal);
		} else if (e.key === 'ArrowDown' || e.key === 'ArrowLeft') {
			e.preventDefault();
			const newVal = clampStep(value - step);
			if (newVal !== value) onchange?.(newVal);
		}
	}
</script>

<div class="knob-wrap">
	{#if label}
		<div class="knob-label">{label}</div>
	{/if}
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<svg
		viewBox="0 0 {size} {size}"
		width={size}
		height={size}
		class="knob-svg"
		class:dragging
		onpointerdown={onPointerDown}
		onpointermove={onPointerMove}
		onpointerup={onPointerUp}
		onpointercancel={onPointerUp}
		onwheel={onWheel}
		onkeydown={onKeydown}
		role="slider"
		aria-valuenow={value}
		aria-valuemin={min}
		aria-valuemax={max}
		aria-label={label || 'Knob'}
		tabindex="0"
	>
		<!-- Background disc -->
		<circle cx={CX} cy={CY} r={R + 5} fill="#141414" stroke="#2a2a2a" stroke-width="1.5" />
		<!-- Track arc (gray) -->
		<path d={arcPath(START_DEG, trackEndDeg, SWEEP_DEG, R)} fill="none" stroke="#2a2a2a" stroke-width="4" stroke-linecap="round" />
		<!-- Value arc (blue) — only draw if non-trivial -->
		{#if valueSweep > 1}
			<path d={arcPath(START_DEG, valueDeg, valueSweep, R)} fill="none" stroke="#4a9eff" stroke-width="4" stroke-linecap="round" />
		{/if}
		<!-- Indicator dot -->
		<circle cx={dot.x} cy={dot.y} r={size * 0.038} fill="#e0e0e0" />
		<!-- Value text in centre -->
		<text
			x={CX} y={CY + 1}
			text-anchor="middle"
			dominant-baseline="middle"
			fill="#bbb"
			font-size={size * 0.2}
			font-family="monospace"
		>{value}</text>
	</svg>
</div>

<style>
	.knob-wrap {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 3px;
	}
	.knob-svg {
		cursor: ns-resize;
		user-select: none;
		touch-action: none;
		outline: none;
	}
	.knob-svg:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
		border-radius: 50%;
	}
	.knob-svg.dragging { cursor: grabbing; }
	.knob-label {
		font-size: 0.62rem;
		color: #777;
		text-transform: uppercase;
		letter-spacing: 0.07em;
		font-family: monospace;
	}
</style>
