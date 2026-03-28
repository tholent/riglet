import { writable } from 'svelte/store';
import type { LayoutConfig } from './types.js';
import { DEFAULT_LAYOUTS, DEFAULT_LAYOUT_IDS } from './defaults.js';

const STORAGE_KEY_ACTIVE = 'riglet:active-layout';
const STORAGE_KEY_CUSTOM = 'riglet:custom-layouts';

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function readCustomLayouts(): LayoutConfig[] {
	if (typeof localStorage === 'undefined') return [];
	try {
		const raw = localStorage.getItem(STORAGE_KEY_CUSTOM);
		if (!raw) return [];
		const parsed = JSON.parse(raw) as unknown;
		if (!Array.isArray(parsed)) return [];
		return parsed as LayoutConfig[];
	} catch {
		return [];
	}
}

function writeCustomLayouts(layouts: LayoutConfig[]): void {
	if (typeof localStorage === 'undefined') return;
	localStorage.setItem(STORAGE_KEY_CUSTOM, JSON.stringify(layouts));
}

function readActiveId(): string {
	if (typeof localStorage === 'undefined') return DEFAULT_LAYOUTS[0].id;
	return localStorage.getItem(STORAGE_KEY_ACTIVE) ?? DEFAULT_LAYOUTS[0].id;
}

function resolveLayout(id: string, customs: LayoutConfig[]): LayoutConfig {
	const all = [...DEFAULT_LAYOUTS, ...customs];
	return all.find((l) => l.id === id) ?? DEFAULT_LAYOUTS[0];
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

const _customLayouts = writable<LayoutConfig[]>(readCustomLayouts());
export const activeLayout = writable<LayoutConfig>(
	resolveLayout(readActiveId(), readCustomLayouts()),
);

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/** Load a layout by ID and set it as active. */
export function loadLayout(id: string): void {
	_customLayouts.update((customs) => {
		const layout = resolveLayout(id, customs);
		activeLayout.set(layout);
		if (typeof localStorage !== 'undefined') {
			localStorage.setItem(STORAGE_KEY_ACTIVE, layout.id);
		}
		return customs;
	});
}

/** Persist a layout (create or replace). */
export function saveLayout(layout: LayoutConfig): void {
	_customLayouts.update((customs) => {
		const idx = customs.findIndex((l) => l.id === layout.id);
		const next = idx >= 0 ? customs.with(idx, layout) : [...customs, layout];
		writeCustomLayouts(next);
		// If this is the active layout, refresh it
		activeLayout.update((active) => (active.id === layout.id ? layout : active));
		return next;
	});
}

/** Return all available layouts (defaults + custom). */
export function listLayouts(): LayoutConfig[] {
	let customs: LayoutConfig[] = [];
	_customLayouts.subscribe((v) => (customs = v))();
	return [...DEFAULT_LAYOUTS, ...customs];
}

/** Serialize a layout to a JSON string for file export. */
export function exportLayout(layout: LayoutConfig): string {
	return JSON.stringify(layout, null, 2);
}

/** Parse a JSON string and add the layout to custom layouts. Returns the parsed layout. */
export function importLayout(jsonStr: string): LayoutConfig {
	const parsed = JSON.parse(jsonStr) as LayoutConfig;
	if (!parsed.id || !parsed.name || !Array.isArray(parsed.panels)) {
		throw new Error('Invalid layout JSON: missing required fields');
	}
	saveLayout(parsed);
	return parsed;
}

/** Delete a custom layout by ID. Throws if attempting to delete a default layout. */
export function deleteLayout(id: string): void {
	if (DEFAULT_LAYOUT_IDS.has(id)) {
		throw new Error(`Cannot delete default layout "${id}"`);
	}
	_customLayouts.update((customs) => {
		const next = customs.filter((l) => l.id !== id);
		writeCustomLayouts(next);
		// If deleted layout was active, fall back to default
		activeLayout.update((active) => {
			if (active.id === id) {
				const fallback = DEFAULT_LAYOUTS[0];
				if (typeof localStorage !== 'undefined') {
					localStorage.setItem(STORAGE_KEY_ACTIVE, fallback.id);
				}
				return fallback;
			}
			return active;
		});
		return next;
	});
}
