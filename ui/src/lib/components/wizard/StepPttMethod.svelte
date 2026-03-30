<script lang="ts">
	import type { RadioConfig } from '$lib/types.js';

	interface Props {
		radios: RadioConfig[];
		onUpdate: (radios: RadioConfig[]) => void;
	}
	let { radios, onUpdate }: Props = $props();

	const PTT_METHODS: { value: RadioConfig['ptt_method']; label: string; description: string }[] = [
		{ value: 'cat', label: 'CAT', description: 'PTT via CAT command (recommended for most radios)' },
		{ value: 'vox', label: 'VOX', description: 'Voice-activated transmit — no hardware PTT needed' },
		{ value: 'rts', label: 'RTS', description: 'PTT via serial RTS line' },
		{ value: 'dtr', label: 'DTR', description: 'PTT via serial DTR line' },
	];

	function updatePtt(index: number, method: RadioConfig['ptt_method']) {
		onUpdate(radios.map((r, i) => (i === index ? { ...r, ptt_method: method } : r)));
	}
</script>

<div class="step">
	<h2>PTT Method</h2>
	<p>Choose how each radio switches to transmit mode.</p>

	{#each radios as radio, i (radio.id)}
		<div class="radio-section">
			<h3>{radio.name}</h3>
			{#if radio.type === 'simulated'}
				<p class="sim-note">Simulated radio — PTT is handled in software, no hardware method needed.</p>
			{:else}
				<div class="options">
					{#each PTT_METHODS as method (method.value)}
						<label class="option" class:active={radio.ptt_method === method.value}>
							<input
								type="radio"
								name={`ptt-${radio.id}`}
								value={method.value}
								checked={radio.ptt_method === method.value}
								onchange={() => updatePtt(i, method.value)}
							/>
							<span class="method-label">{method.label}</span>
							<span class="method-desc">{method.description}</span>
						</label>
					{/each}
				</div>
			{/if}
		</div>
	{/each}

	{#if radios.length === 0}
		<p class="hint">No radios configured yet. Go back and add radios first.</p>
	{/if}
</div>

<style>
	.step h2 { margin-top: 0; }
	.hint { color: #888; }

	.sim-note {
		color: #7a5;
		font-size: 0.9rem;
		margin: 0;
		padding: 8px 10px;
		background: rgba(119, 170, 85, 0.08);
		border-radius: 4px;
		border: 1px solid rgba(119, 170, 85, 0.25);
	}

	.radio-section {
		border: 1px solid #444;
		border-radius: 6px;
		padding: 16px;
		margin-bottom: 12px;
		background: #1a1a1a;
	}

	.radio-section h3 { margin: 0 0 12px; }

	.options {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 8px;
	}

	.option {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: 12px;
		border: 1px solid #444;
		border-radius: 4px;
		cursor: pointer;
		transition: border-color 0.15s, background 0.15s;
	}

	.option.active {
		border-color: #4a9eff;
		background: rgba(74, 158, 255, 0.1);
	}

	.option input[type="radio"] {
		display: none;
	}

	.method-label {
		font-weight: 700;
		font-size: 1rem;
	}

	.method-desc {
		font-size: 0.8rem;
		color: #888;
	}
</style>
