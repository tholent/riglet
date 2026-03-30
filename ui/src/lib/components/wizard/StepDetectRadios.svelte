<script lang="ts">
	import { getSerialDevices, getHamlibModels, postCatTest } from '$lib/api.js';
	import type { RadioConfig, SerialDevice } from '$lib/types.js';

	interface Props {
		radios: RadioConfig[];
		onUpdate: (radios: RadioConfig[]) => void;
	}
	let { radios, onUpdate }: Props = $props();

	let devices = $state<SerialDevice[]>([]);
	let hamlibModels = $state<{ id: number; name: string }[]>([]);
	let loading = $state(true);
	let catTestResults = $state<Record<string, { success: boolean; freq?: number; error?: string }>>({});
	let testingCat = $state<Record<string, boolean>>({});

	let autoPopulateDone = false;

	$effect(() => {
		Promise.all([getSerialDevices(), getHamlibModels()])
			.then(([devs, models]) => {
				devices = devs;
				hamlibModels = models;
				// Auto-populate only on first load and only when no radios are configured yet
				if (!autoPopulateDone && radios.length === 0) {
					autoPopulateDone = true;
					const newRadios = devs.map((d, i): RadioConfig => ({
						id: `radio${i + 1}`,
						name: d.description || `Radio ${i + 1}`,
						type: 'real',
						hamlib_model: d.guessed_model ?? 1,
						serial_port: d.port,
						baud_rate: 19200,
						ptt_method: 'cat',
						audio_source: '',
						audio_sink: '',
						rigctld_port: 4532 + i,
						enabled: false,
						polling_interval_ms: 100,
						bands: [],
					}));
					if (newRadios.length > 0) {
						onUpdate(newRadios);
					}
				}
			})
			.catch(console.error)
			.finally(() => { loading = false; });
	});

	function updateRadio(index: number, patch: Partial<RadioConfig>) {
		const updated = radios.map((r, i) => (i === index ? { ...r, ...patch } : r));
		onUpdate(updated);
	}

	function removeRadio(index: number) {
		onUpdate(radios.filter((_, i) => i !== index));
	}

	function addManual() {
		const next = radios.length + 1;
		onUpdate([
			...radios,
			{
				id: `radio${next}`,
				name: `Radio ${next}`,
				type: 'real',
				hamlib_model: 1,
				serial_port: '',
				baud_rate: 19200,
				ptt_method: 'cat',
				audio_source: '',
				audio_sink: '',
				rigctld_port: 4532 + next - 1,
				enabled: false,
				polling_interval_ms: 100,
				bands: [],
			},
		]);
	}

	function addSimulated() {
		const next = radios.length + 1;
		onUpdate([
			...radios,
			{
				id: `sim${next}`,
				name: `Simulated Radio ${next}`,
				type: 'simulated',
				hamlib_model: 1,
				serial_port: '',
				baud_rate: 19200,
				ptt_method: 'cat',
				audio_source: '',
				audio_sink: '',
				rigctld_port: 4532 + next - 1,
				enabled: true,
				polling_interval_ms: 100,
				bands: [],
			},
		]);
	}

	async function testCat(radio: RadioConfig, index: number) {
		testingCat[index] = true;
		try {
			const result = await postCatTest(radio.id);
			catTestResults[index] = result;
		} catch (e) {
			catTestResults[index] = { success: false, error: String(e) };
		} finally {
			testingCat[index] = false;
		}
	}
</script>

<div class="step">
	<h2>Detect Radios</h2>

	{#if loading}
		<p>Scanning for connected devices...</p>
	{:else}
		{#if devices.length === 0}
			<p class="hint">No serial devices detected. You can add a radio manually.</p>
		{/if}

		{#each radios as radio, i (radio.id)}
			<div class="radio-card">
				<div class="card-header">
					<input
						type="text"
						value={radio.name}
						oninput={(e) => updateRadio(i, { name: (e.target as HTMLInputElement).value })}
						placeholder="Radio name"
					/>
					<button class="remove-btn" onclick={() => removeRadio(i)} aria-label="Remove">✕</button>
				</div>

				{#if radio.type === 'simulated'}
					<p class="sim-note">Simulated radio — no hardware required. Frequency, mode, and PTT are handled in software.</p>
				{:else}
					<div class="fields">
						<label>
							Serial Port
							<input
								type="text"
								value={radio.serial_port}
								oninput={(e) => updateRadio(i, { serial_port: (e.target as HTMLInputElement).value })}
								placeholder="/dev/ttyUSB0"
							/>
						</label>

						<label>
							Hamlib Model
							<select
								value={radio.hamlib_model}
								onchange={(e) => updateRadio(i, { hamlib_model: parseInt((e.target as HTMLSelectElement).value) })}
							>
								{#each hamlibModels as m (m.id)}
									<option value={m.id}>{m.id} — {m.name}</option>
								{/each}
							</select>
						</label>

						<label>
							Baud Rate
							<input
								type="number"
								value={radio.baud_rate}
								oninput={(e) => updateRadio(i, { baud_rate: parseInt((e.target as HTMLInputElement).value) })}
							/>
						</label>
					</div>

					<div class="card-footer">
						<button
							onclick={() => testCat(radio, i)}
							disabled={testingCat[i] || !radio.serial_port}
						>
							{testingCat[i] ? 'Testing...' : 'Test CAT'}
						</button>
						{#if catTestResults[i]}
							{#if catTestResults[i].success}
								<span class="ok">Connected — {catTestResults[i].freq?.toFixed(3)} MHz</span>
							{:else}
								<span class="err">{catTestResults[i].error}</span>
							{/if}
						{/if}
					</div>
				{/if}
			</div>
		{/each}

		<div class="add-btns">
			<button class="add-btn" onclick={addManual}>+ Add Real Radio</button>
			<button
				class="add-btn sim"
				onclick={addSimulated}
				disabled={radios.some((r) => r.type === 'simulated')}
				title={radios.some((r) => r.type === 'simulated') ? 'Only one simulated radio is supported' : undefined}
			>+ Add Simulated Radio</button>
		</div>
	{/if}
</div>

<style>
	.step h2 { margin-top: 0; }
	.hint { color: #888; }

	.radio-card {
		border: 1px solid #444;
		border-radius: 6px;
		padding: 16px;
		margin-bottom: 12px;
		background: #1a1a1a;
	}

	.card-header {
		display: flex;
		gap: 8px;
		align-items: center;
		margin-bottom: 12px;
	}

	.card-header input { flex: 1; font-weight: 600; }

	.fields {
		display: grid;
		grid-template-columns: 1fr 1fr 1fr;
		gap: 12px;
		margin-bottom: 12px;
	}

	label {
		display: flex;
		flex-direction: column;
		gap: 4px;
		font-size: 0.85rem;
		color: #aaa;
	}

	input, select {
		padding: 6px 8px;
		border: 1px solid #555;
		border-radius: 4px;
		background: #111;
		color: inherit;
	}

	.card-footer {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.ok { color: #4caf50; font-size: 0.9rem; }
	.err { color: #f44336; font-size: 0.9rem; }

	.remove-btn {
		background: none;
		border: none;
		color: #888;
		cursor: pointer;
		font-size: 1rem;
		padding: 2px 6px;
	}

	.remove-btn:hover { color: #f44; }

	.add-btns {
		display: flex;
		gap: 8px;
		margin-top: 8px;
	}

	.add-btn {
		flex: 1;
		padding: 8px 16px;
		border: 1px dashed #555;
		border-radius: 4px;
		background: none;
		color: #888;
		cursor: pointer;
	}

	.add-btn:hover:not(:disabled) { border-color: #aaa; color: #fff; }
	.add-btn:disabled { opacity: 0.35; cursor: not-allowed; }

	.add-btn.sim { border-color: #7a5; color: #7a5; }
	.add-btn.sim:hover { border-color: #9c7; color: #9c7; }

	.sim-note {
		color: #7a5;
		font-size: 0.9rem;
		margin: 0 0 8px;
		padding: 8px 10px;
		background: rgba(119, 170, 85, 0.08);
		border-radius: 4px;
		border: 1px solid rgba(119, 170, 85, 0.25);
	}

	button:disabled { opacity: 0.5; cursor: not-allowed; }

	button:not(.remove-btn):not(.add-btn) {
		padding: 6px 14px;
		background: #333;
		border: 1px solid #555;
		border-radius: 4px;
		color: inherit;
		cursor: pointer;
	}

	button:not(.remove-btn):not(.add-btn):hover:not(:disabled) {
		background: #444;
	}
</style>
