<script lang="ts">
	import type { ControlWebSocket } from '$lib/websocket.js';
	import type { PresetConfig } from '$lib/types.js';
	import { getPresets, createPreset, deletePreset, importPresets, exportPresets } from '$lib/api.js';
	import { onMount } from 'svelte';

	interface Props {
		radioId: string;
		currentFreqMhz: number;
		controlWs: ControlWebSocket | null;
		onPresetsChange?: (presets: PresetConfig[]) => void;
	}
	let { currentFreqMhz, controlWs, onPresetsChange }: Props = $props();

	let presets = $state<PresetConfig[]>([]);
	let loading = $state(false);
	let error = $state<string | null>(null);
	let fileInput: HTMLInputElement;

	async function loadPresets() {
		loading = true;
		error = null;
		try {
			const result = await getPresets();
			presets = result.presets;
			onPresetsChange?.(presets);
		} catch (e) {
			error = 'Failed to load presets';
			console.error('[PresetSelector]', e);
		} finally {
			loading = false;
		}
	}

	onMount(loadPresets);

	// Group presets by band
	const presetsByBand = $derived(() => {
		const map = new Map<string, PresetConfig[]>();
		for (const p of presets) {
			const list = map.get(p.band) ?? [];
			list.push(p);
			map.set(p.band, list);
		}
		return map;
	});

	const bandOrder = $derived(() => Array.from(presetsByBand().keys()).sort());

	function selectPreset(preset: PresetConfig) {
		if (!controlWs) return;
		controlWs.send({ type: 'freq', freq: preset.frequency_mhz });
		if (preset.mode) {
			controlWs.send({ type: 'mode', mode: preset.mode });
		}
	}

	async function saveCurrentAsPreset() {
		const name = prompt('Preset name:');
		if (!name?.trim()) return;

		// Determine band from frequency
		const band = guessBand(currentFreqMhz);

		const preset: PresetConfig = {
			id: crypto.randomUUID(),
			name: name.trim(),
			band,
			frequency_mhz: currentFreqMhz,
			offset_mhz: 0,
			ctcss_tone: null,
			mode: null,
		};

		try {
			const result = await createPreset(preset);
			presets = result.presets;
			onPresetsChange?.(presets);
		} catch (e) {
			alert('Failed to save preset');
			console.error('[PresetSelector]', e);
		}
	}

	async function handleImport() {
		fileInput?.click();
	}

	async function onFileChange(e: Event) {
		const file = (e.target as HTMLInputElement).files?.[0];
		if (!file) return;

		try {
			const text = await file.text();
			const data = JSON.parse(text) as { presets?: PresetConfig[] };
			if (!Array.isArray(data.presets)) {
				alert('Invalid preset file format');
				return;
			}
			const result = await importPresets(data.presets);
			presets = result.presets;
			onPresetsChange?.(presets);
		} catch (e) {
			alert('Failed to import presets');
			console.error('[PresetSelector]', e);
		} finally {
			// Reset so the same file can be re-imported
			(e.target as HTMLInputElement).value = '';
		}
	}

	async function removePreset(preset: PresetConfig) {
		try {
			const result = await deletePreset(preset.id);
			presets = result.presets;
			onPresetsChange?.(presets);
		} catch (e) {
			alert('Failed to delete preset');
			console.error('[PresetSelector]', e);
		}
	}

	async function handleExport() {
		try {
			const result = await exportPresets();
			const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = 'riglet-presets.json';
			a.click();
			URL.revokeObjectURL(url);
		} catch (e) {
			alert('Failed to export presets');
			console.error('[PresetSelector]', e);
		}
	}

	/** Very rough band guess from frequency. */
	function guessBand(mhz: number): string {
		if (mhz >= 1.8 && mhz <= 2.0) return '160m';
		if (mhz >= 3.5 && mhz <= 4.0) return '80m';
		if (mhz >= 7.0 && mhz <= 7.3) return '40m';
		if (mhz >= 10.1 && mhz <= 10.15) return '30m';
		if (mhz >= 14.0 && mhz <= 14.35) return '20m';
		if (mhz >= 18.068 && mhz <= 18.168) return '17m';
		if (mhz >= 21.0 && mhz <= 21.45) return '15m';
		if (mhz >= 24.89 && mhz <= 24.99) return '12m';
		if (mhz >= 28.0 && mhz <= 29.7) return '10m';
		if (mhz >= 50.0 && mhz <= 54.0) return '6m';
		if (mhz >= 144.0 && mhz <= 148.0) return '2m';
		if (mhz >= 420.0 && mhz <= 450.0) return '70cm';
		return 'other';
	}
</script>

<div class="preset-selector" aria-label="Frequency presets">
	<div class="toolbar">
		<span class="label">Presets</span>
		<button class="btn" onclick={saveCurrentAsPreset} aria-label="Save current frequency as preset">
			Save current
		</button>
		<button class="btn" onclick={handleImport} aria-label="Import presets from JSON file">
			Import
		</button>
		<button class="btn" onclick={handleExport} aria-label="Export presets to JSON file">
			Export
		</button>
		<!-- Hidden file input for import -->
		<input
			bind:this={fileInput}
			type="file"
			accept="application/json,.json"
			style="display:none"
			onchange={onFileChange}
			aria-hidden="true"
		/>
	</div>

	{#if loading}
		<p class="hint">Loading…</p>
	{:else if error}
		<p class="hint error">{error}</p>
	{:else if presets.length === 0}
		<p class="hint">No presets saved.</p>
	{:else}
		<div class="preset-list" role="list">
			{#each bandOrder() as band (band)}
				<div class="band-group">
					<span class="band-label">{band}</span>
					{#each presetsByBand().get(band) ?? [] as preset (preset.id)}
						<div class="preset-row">
							<button
								class="preset-item"
								onclick={() => selectPreset(preset)}
								aria-label={`Tune to preset ${preset.name} at ${preset.frequency_mhz} MHz`}
							>
								<span class="preset-name">{preset.name}</span>
								<span class="preset-freq">{preset.frequency_mhz.toFixed(3)}</span>
							</button>
							<button
								class="delete-btn"
								onclick={() => removePreset(preset)}
								aria-label={`Delete preset ${preset.name}`}
							>✕</button>
						</div>
					{/each}
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.preset-selector {
		font-size: 0.82rem;
		color: #ccc;
		height: 100%;
		display: flex;
		flex-direction: column;
	}

	.toolbar {
		display: flex;
		align-items: center;
		gap: 6px;
		flex-wrap: wrap;
		margin-bottom: 8px;
		flex-shrink: 0;
	}

	.label {
		font-weight: 600;
		font-size: 0.8rem;
		color: #bbb;
		margin-right: 4px;
	}

	.btn {
		padding: 3px 9px;
		font-size: 0.75rem;
		background: #1a1a1a;
		border: 1px solid #3a3a3a;
		border-radius: 4px;
		color: #aaa;
		cursor: pointer;
	}

	.btn:hover {
		background: #252525;
		border-color: #555;
		color: #ddd;
	}

	.btn:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
	}

	.preset-list {
		display: flex;
		flex-direction: column;
		gap: 4px;
		flex: 1;
		overflow-y: auto;
	}

	.band-group {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.band-label {
		font-size: 0.7rem;
		color: #666;
		font-weight: 600;
		padding: 2px 0 1px;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.preset-row {
		display: flex;
		align-items: center;
		gap: 3px;
	}

	.preset-row .delete-btn {
		flex-shrink: 0;
		width: 20px;
		height: 20px;
		padding: 0;
		background: none;
		border: 1px solid transparent;
		border-radius: 3px;
		color: #444;
		cursor: pointer;
		font-size: 0.65rem;
		opacity: 0;
		transition: opacity 0.1s, color 0.1s, border-color 0.1s;
	}

	.preset-row:hover .delete-btn {
		opacity: 1;
	}

	.preset-row .delete-btn:hover {
		color: #f44336;
		border-color: #f44336;
	}

	.preset-row .delete-btn:focus-visible {
		opacity: 1;
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
	}

	.preset-item {
		flex: 1;
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 4px 8px;
		background: #151515;
		border: 1px solid #2a2a2a;
		border-radius: 3px;
		color: #ccc;
		cursor: pointer;
		text-align: left;
		font-size: 0.8rem;
		min-width: 0;
	}

	.preset-item:hover {
		background: #1f1f1f;
		border-color: #4a9eff;
		color: #fff;
	}

	.preset-item:focus-visible {
		outline: 2px solid #4a9eff;
		outline-offset: 2px;
	}

	.preset-name {
		flex: 1;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.preset-freq {
		font-family: 'Courier New', monospace;
		font-size: 0.75rem;
		color: #4cff8a;
		margin-left: 8px;
		flex-shrink: 0;
	}

	.hint {
		color: #666;
		font-size: 0.78rem;
		margin: 4px 0;
	}

	.hint.error {
		color: #f44336;
	}
</style>
