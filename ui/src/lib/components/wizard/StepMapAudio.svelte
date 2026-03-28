<script lang="ts">
	import { getAudioDevices } from '$lib/api.js';
	import { claimedResources } from '$lib/stores.js';
	import type { AudioDevice, RadioConfig } from '$lib/types.js';

	interface Props {
		radios: RadioConfig[];
		onUpdate: (radios: RadioConfig[]) => void;
	}
	let { radios, onUpdate }: Props = $props();

	let audioDevices = $state<AudioDevice[]>([]);

	$effect(() => {
		getAudioDevices()
			.then((devs) => { audioDevices = devs; })
			.catch(console.error);
	});

	function updateRadio(index: number, patch: Partial<RadioConfig>) {
		const old = radios[index];
		const updated = { ...old, ...patch };

		claimedResources.update((claimed) => {
			const next = { ...claimed };
			// Release old claims
			if (old.audio_source && next[old.audio_source] === old.id) delete next[old.audio_source];
			if (old.audio_sink && next[old.audio_sink] === old.id) delete next[old.audio_sink];
			// Set new claims
			if (updated.audio_source) next[updated.audio_source] = updated.id;
			if (updated.audio_sink) next[updated.audio_sink] = updated.id;
			return next;
		});

		onUpdate(radios.map((r, i) => (i === index ? updated : r)));
	}

	function getClaimedBy(deviceId: string, currentRadioId: string): string | null {
		let claimed: Record<string, string> = {};
		claimedResources.subscribe((v) => { claimed = v; })();
		const owner = claimed[deviceId];
		return owner && owner !== currentRadioId ? (radios.find((r) => r.id === owner)?.name ?? owner) : null;
	}
</script>

<div class="step">
	<h2>Map Audio Devices</h2>
	<p>Assign audio input and output devices to each radio.</p>

	{#each radios as radio, i}
		<div class="radio-section">
			<h3>{radio.name}</h3>

			{#if radio.type === 'simulated'}
				<p class="sim-note">Simulated radio — no audio device needed.</p>
			{:else}
				<div class="fields">
					<label>
						Audio Source (RX)
						<select
							value={radio.audio_source}
							onchange={(e) => updateRadio(i, { audio_source: (e.target as HTMLSelectElement).value })}
						>
							<option value="">— none —</option>
							{#each audioDevices as d}
								{@const claimer = getClaimedBy(d.source, radio.id)}
								<option value={d.source} disabled={claimer !== null}>
									{d.name}{claimer ? ` (In use by ${claimer})` : ''}
								</option>
							{/each}
						</select>
					</label>

					<label>
						Audio Sink (TX)
						<select
							value={radio.audio_sink}
							onchange={(e) => updateRadio(i, { audio_sink: (e.target as HTMLSelectElement).value })}
						>
							<option value="">— none —</option>
							{#each audioDevices as d}
								{@const claimer = getClaimedBy(d.sink, radio.id)}
								<option value={d.sink} disabled={claimer !== null}>
									{d.name}{claimer ? ` (In use by ${claimer})` : ''}
								</option>
							{/each}
						</select>
					</label>
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

	.fields {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
	}

	label {
		display: flex;
		flex-direction: column;
		gap: 4px;
		font-size: 0.85rem;
		color: #aaa;
	}

	select {
		padding: 6px 8px;
		border: 1px solid #555;
		border-radius: 4px;
		background: #111;
		color: inherit;
	}
</style>
