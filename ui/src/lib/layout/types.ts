export type PanelComponent =
	| 'visualization'
	| 'frequency'
	| 'band-selector'
	| 'mode-selector'
	| 'ptt'
	| 'smeter'
	| 'audio'
	| 'dsp'
	| 'lufs-meter'
	| 'presets'
	| 'vfo'
	| 'cat-extended';

export interface PanelPosition {
	row: number;
	col: number;
	rowSpan: number;
	colSpan: number;
}

export interface LayoutPanel {
	id: string;
	component: PanelComponent;
	position: PanelPosition;
}

export interface LayoutConfig {
	id: string;
	name: string;
	columns: number;
	/** CSS grid-template-columns value. Defaults to repeat(columns, 1fr) if omitted. */
	columnWidths?: string;
	rows: number;
	panels: LayoutPanel[];
}
