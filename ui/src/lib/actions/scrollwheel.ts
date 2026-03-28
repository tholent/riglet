/**
 * Svelte action for scroll-wheel interaction on dial controls.
 *
 * Captures wheel events only when the pointer is over the element,
 * preventing scroll hijacking elsewhere on the page.
 *
 * Usage:
 *   <div use:scrollWheel={{ onDelta: (d) => nudge(d), step: 1 }}>...</div>
 */

export interface ScrollWheelParams {
	/** Called with +1 (scroll up/forward) or -1 (scroll down/backward). */
	onDelta: (delta: number) => void;
	/** Not used in the action itself, but kept for documentation purposes.
	 *  The caller decides how to interpret delta (e.g. step size). */
	step?: number;
}

/**
 * Svelte action that calls `params.onDelta(+1 | -1)` on wheel events
 * when the pointer is hovering over the element.
 */
export function scrollWheel(
	node: HTMLElement,
	params: ScrollWheelParams
): { update(newParams: ScrollWheelParams): void; destroy(): void } {
	let hovered = false;
	let currentParams = params;

	function onPointerEnter() {
		hovered = true;
	}

	function onPointerLeave() {
		hovered = false;
	}

	function onWheel(event: WheelEvent) {
		if (!hovered) return;
		event.preventDefault();
		// deltaY > 0 = scroll down = decrease; < 0 = scroll up = increase
		const delta = event.deltaY < 0 ? 1 : -1;
		currentParams.onDelta(delta);
	}

	node.addEventListener('pointerenter', onPointerEnter);
	node.addEventListener('pointerleave', onPointerLeave);
	// passive: false so we can call preventDefault and stop page scroll
	node.addEventListener('wheel', onWheel, { passive: false });

	return {
		update(newParams: ScrollWheelParams) {
			currentParams = newParams;
		},
		destroy() {
			node.removeEventListener('pointerenter', onPointerEnter);
			node.removeEventListener('pointerleave', onPointerLeave);
			node.removeEventListener('wheel', onWheel);
		},
	};
}
