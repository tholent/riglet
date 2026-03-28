import type { LayoutConfig } from './types.js';

/**
 * Voice Operating — matches the current two-column layout:
 *   col 1: visualization panel (spans most rows), with mode/freq/band/presets stacked above
 *   col 2: ptt+lufs, smeter, audio, dsp
 */
const VOICE_OPERATING: LayoutConfig = {
	id: 'voice-operating',
	name: 'Voice Operating',
	columns: 2,
	rows: 6,
	panels: [
		{ id: 'mode', component: 'mode-selector', position: { row: 1, col: 1, rowSpan: 1, colSpan: 1 } },
		{ id: 'freq', component: 'frequency', position: { row: 2, col: 1, rowSpan: 1, colSpan: 1 } },
		{ id: 'band', component: 'band-selector', position: { row: 3, col: 1, rowSpan: 1, colSpan: 1 } },
		{ id: 'presets', component: 'presets', position: { row: 4, col: 1, rowSpan: 1, colSpan: 1 } },
		{ id: 'viz', component: 'visualization', position: { row: 5, col: 1, rowSpan: 2, colSpan: 1 } },
		{ id: 'ptt', component: 'ptt', position: { row: 1, col: 2, rowSpan: 1, colSpan: 1 } },
		{ id: 'lufs', component: 'lufs-meter', position: { row: 2, col: 2, rowSpan: 1, colSpan: 1 } },
		{ id: 'smeter', component: 'smeter', position: { row: 3, col: 2, rowSpan: 1, colSpan: 1 } },
		{ id: 'audio', component: 'audio', position: { row: 4, col: 2, rowSpan: 1, colSpan: 1 } },
		{ id: 'dsp', component: 'dsp', position: { row: 5, col: 2, rowSpan: 2, colSpan: 1 } },
	],
};

/**
 * Digital Modes — compact waterfall, more controls visible.
 *   Wider control column, smaller visualization, VFO/CTCSS shown.
 */
const DIGITAL_MODES: LayoutConfig = {
	id: 'digital-modes',
	name: 'Digital Modes',
	columns: 2,
	rows: 7,
	panels: [
		{ id: 'mode', component: 'mode-selector', position: { row: 1, col: 1, rowSpan: 1, colSpan: 1 } },
		{ id: 'freq', component: 'frequency', position: { row: 2, col: 1, rowSpan: 1, colSpan: 1 } },
		{ id: 'band', component: 'band-selector', position: { row: 3, col: 1, rowSpan: 1, colSpan: 1 } },
		{ id: 'viz', component: 'visualization', position: { row: 4, col: 1, rowSpan: 4, colSpan: 1 } },
		{ id: 'vfo', component: 'vfo', position: { row: 1, col: 2, rowSpan: 1, colSpan: 1 } },
		{ id: 'smeter', component: 'smeter', position: { row: 2, col: 2, rowSpan: 1, colSpan: 1 } },
		{ id: 'cat', component: 'cat-extended', position: { row: 3, col: 2, rowSpan: 1, colSpan: 1 } },
		{ id: 'audio', component: 'audio', position: { row: 4, col: 2, rowSpan: 1, colSpan: 1 } },
		{ id: 'dsp', component: 'dsp', position: { row: 5, col: 2, rowSpan: 1, colSpan: 1 } },
		{ id: 'lufs', component: 'lufs-meter', position: { row: 6, col: 2, rowSpan: 1, colSpan: 1 } },
		{ id: 'presets', component: 'presets', position: { row: 7, col: 2, rowSpan: 1, colSpan: 1 } },
	],
};

/**
 * SWL (Short Wave Listener) — large waterfall, no PTT/TX controls.
 *   Single column with large visualization dominating.
 */
const SWL: LayoutConfig = {
	id: 'swl',
	name: 'SWL',
	columns: 2,
	rows: 5,
	panels: [
		{ id: 'freq', component: 'frequency', position: { row: 1, col: 1, rowSpan: 1, colSpan: 1 } },
		{ id: 'band', component: 'band-selector', position: { row: 2, col: 1, rowSpan: 1, colSpan: 1 } },
		{ id: 'viz', component: 'visualization', position: { row: 3, col: 1, rowSpan: 3, colSpan: 1 } },
		{ id: 'mode', component: 'mode-selector', position: { row: 1, col: 2, rowSpan: 1, colSpan: 1 } },
		{ id: 'smeter', component: 'smeter', position: { row: 2, col: 2, rowSpan: 1, colSpan: 1 } },
		{ id: 'lufs', component: 'lufs-meter', position: { row: 3, col: 2, rowSpan: 1, colSpan: 1 } },
		{ id: 'audio', component: 'audio', position: { row: 4, col: 2, rowSpan: 1, colSpan: 1 } },
		{ id: 'dsp', component: 'dsp', position: { row: 5, col: 2, rowSpan: 1, colSpan: 1 } },
	],
};

export const DEFAULT_LAYOUTS: LayoutConfig[] = [VOICE_OPERATING, DIGITAL_MODES, SWL];

export const DEFAULT_LAYOUT_IDS = new Set(DEFAULT_LAYOUTS.map((l) => l.id));
