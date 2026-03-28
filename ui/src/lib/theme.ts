/**
 * Theme infrastructure for Riglet.
 *
 * Manages light/dark/system theme preference, persisted in localStorage.
 * Sets a `data-theme` attribute on `<html>` which CSS custom properties
 * target to switch the colour palette.
 */

export type ThemeMode = 'light' | 'dark' | 'system';

const STORAGE_KEY = 'riglet-theme';

/** Return the resolved CSS theme ("light" or "dark") from a ThemeMode. */
function resolveMode(mode: ThemeMode): 'light' | 'dark' {
	if (mode === 'system') {
		return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
	}
	return mode;
}

/**
 * Read preference from localStorage, fall back to `prefers-color-scheme`.
 * Sets `data-theme` on `<html>` immediately.
 * Call once at app startup (e.g. in +layout.svelte onMount).
 */
export function initTheme(): void {
	if (typeof window === 'undefined') return;

	const stored = localStorage.getItem(STORAGE_KEY) as ThemeMode | null;
	const mode: ThemeMode = stored ?? 'system';
	applyTheme(mode);

	// React to OS preference changes when mode is 'system'
	window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', () => {
		const current = getTheme();
		if (current === 'system') {
			applyTheme('system');
		}
	});
}

/** Persist mode to localStorage and update `data-theme` on `<html>`. */
export function setTheme(mode: ThemeMode): void {
	if (typeof window === 'undefined') return;
	localStorage.setItem(STORAGE_KEY, mode);
	applyTheme(mode);
}

/** Read the currently stored ThemeMode (may be 'system'). */
export function getTheme(): ThemeMode {
	if (typeof window === 'undefined') return 'system';
	return (localStorage.getItem(STORAGE_KEY) as ThemeMode | null) ?? 'system';
}

function applyTheme(mode: ThemeMode): void {
	const resolved = resolveMode(mode);
	document.documentElement.setAttribute('data-theme', resolved);
}
