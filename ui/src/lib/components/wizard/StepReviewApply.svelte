<script lang="ts">
	import type { RadioConfig, RigletConfig } from '$lib/types.js';

	interface Props {
		config: RigletConfig;
		onApply: () => Promise<void>;
		applying: boolean;
		applyError: string | null;
	}
	let { config, onApply, applying, applyError }: Props = $props();

	const PTT_LABELS: Record<RadioConfig['ptt_method'], string> = {
		cat: 'CAT',
		vox: 'VOX',
		rts: 'RTS',
		dtr: 'DTR',
	};
</script>

<div class="step">
	<h2>Review & Apply</h2>
	<p>Review your configuration before applying.</p>

	<section>
		<h3>Operator</h3>
		<dl>
			<dt>Callsign</dt><dd>{config.operator.callsign || '—'}</dd>
			<dt>Grid</dt><dd>{config.operator.grid || '—'}</dd>
			<dt>Hostname</dt><dd>{config.network.hostname}.local</dd>
		</dl>
	</section>

	<section>
		<h3>Radios</h3>
		{#if config.radios.length === 0}
			<p class="hint">No radios configured.</p>
		{:else}
			<table>
				<thead>
					<tr>
						<th>Name</th>
						<th>Port</th>
						<th>Model</th>
						<th>Baud</th>
						<th>PTT</th>
						<th>Audio Source</th>
						<th>Audio Sink</th>
					</tr>
				</thead>
				<tbody>
					{#each config.radios as r}
						<tr>
							<td>{r.name}</td>
							<td><code>{r.serial_port || '—'}</code></td>
							<td>{r.hamlib_model}</td>
							<td>{r.baud_rate}</td>
							<td>{PTT_LABELS[r.ptt_method]}</td>
							<td class="mono">{r.audio_source || '—'}</td>
							<td class="mono">{r.audio_sink || '—'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}
	</section>

	{#if applyError}
		<div class="error">{applyError}</div>
	{/if}

	<button class="apply-btn" onclick={onApply} disabled={applying}>
		{applying ? 'Applying...' : 'Apply and restart'}
	</button>
</div>

<style>
	.step h2 { margin-top: 0; }
	.hint { color: #888; }

	section {
		margin-bottom: 24px;
	}

	section h3 { margin-bottom: 8px; }

	dl {
		display: grid;
		grid-template-columns: 140px 1fr;
		gap: 4px 12px;
	}

	dt { color: #888; font-weight: 600; }
	dd { margin: 0; }

	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.9rem;
	}

	th, td {
		text-align: left;
		padding: 6px 10px;
		border-bottom: 1px solid #333;
	}

	th { color: #888; font-weight: 600; }

	.mono { font-family: monospace; font-size: 0.8rem; }

	code { font-size: 0.85rem; }

	.error {
		background: rgba(244, 67, 54, 0.15);
		border: 1px solid #f44336;
		border-radius: 4px;
		padding: 12px;
		color: #f44336;
		margin-bottom: 16px;
	}

	.apply-btn {
		padding: 10px 24px;
		background: #4a9eff;
		border: none;
		border-radius: 4px;
		color: #fff;
		font-size: 1rem;
		font-weight: 600;
		cursor: pointer;
	}

	.apply-btn:hover:not(:disabled) { background: #2a7ee0; }
	.apply-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
