/**
 * RendererRegistry — maps VisualizationMode keys to factory functions.
 *
 * Usage:
 *   import { registerRenderer, createRenderer } from '$lib/viz/base-renderer.js';
 *   import { WaterfallRenderer } from '$lib/viz/waterfall-renderer.js';
 *
 *   registerRenderer('waterfall', () => new WaterfallRenderer());
 *   const renderer = createRenderer('waterfall');
 */

import type { Renderer, RendererFactory, VisualizationMode } from './types.js';

const registry = new Map<VisualizationMode, RendererFactory>();

/**
 * Register a factory for a given visualization mode.
 * Calling this for the same mode again overwrites the previous factory.
 */
export function registerRenderer(mode: VisualizationMode, factory: RendererFactory): void {
	registry.set(mode, factory);
}

/**
 * Instantiate and return a new renderer for the given mode.
 * Throws if no factory is registered for that mode.
 */
export function createRenderer(mode: VisualizationMode): Renderer {
	const factory = registry.get(mode);
	if (!factory) {
		throw new Error(
			`No renderer registered for visualization mode '${mode}'. ` +
				`Registered modes: ${[...registry.keys()].join(', ') || '(none)'}`
		);
	}
	return factory();
}

/**
 * Return all currently registered visualization modes.
 */
export function registeredModes(): VisualizationMode[] {
	return [...registry.keys()];
}
