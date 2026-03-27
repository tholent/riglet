<script lang="ts">
	import { goto } from '$app/navigation';
	import { getConfig, postConfig, postConfigRestart } from '$lib/api.js';
	import { appConfig } from '$lib/stores.js';
	import { waitForRestart } from '$lib/reconnect.js';
	import StepWelcome from '$lib/components/wizard/StepWelcome.svelte';
	import StepDetectRadios from '$lib/components/wizard/StepDetectRadios.svelte';
	import StepMapAudio from '$lib/components/wizard/StepMapAudio.svelte';
	import StepPttMethod from '$lib/components/wizard/StepPttMethod.svelte';
	import StepReviewApply from '$lib/components/wizard/StepReviewApply.svelte';
	import type { RigletConfig } from '$lib/types.js';

	const STEPS = ['Welcome', 'Detect Radios', 'Map Audio', 'PTT Method', 'Review & Apply'];

	let step = $state(0);
	let applying = $state(false);
	let applyError = $state<string | null>(null);

	// Local working copy of config built up through wizard
	let config = $state<RigletConfig>({
		operator: { callsign: '', grid: '' },
		network: { hostname: 'riglet', http_port: 8080 },
		audio: { sample_rate: 16000, chunk_ms: 20 },
		radios: [],
	});

	// Fetch existing config on mount to prefill
	$effect(() => {
		getConfig()
			.then((c) => {
				config = c;
			})
			.catch(() => {
				// Use defaults if no config yet
			});
	});

	// SSE subscription for hotplug events during wizard
	$effect(() => {
		const evtSource = new EventSource('/api/devices/events');
		evtSource.onmessage = () => {
			// Device list changes are handled inside each step via their own effects
		};
		return () => evtSource.close();
	});

	function prev() {
		if (step > 0) step -= 1;
	}

	function next() {
		if (step < STEPS.length - 1) step += 1;
	}

	function updateHostname(hostname: string) {
		config = { ...config, network: { ...config.network, hostname } };
	}

	function updateRadios(radios: RigletConfig['radios']) {
		config = { ...config, radios };
	}

	async function applyAndStart() {
		applying = true;
		applyError = null;

		// Mark all configured radios as enabled if they have required fields
		const radios = config.radios.map((r) => ({
			...r,
			enabled: !!(r.serial_port && r.audio_source && r.audio_sink),
		}));
		const finalConfig = { ...config, radios };

		try {
			await postConfig(finalConfig);
			appConfig.set(finalConfig);

			await postConfigRestart();

			const back = await waitForRestart(30_000);
			if (back) {
				await goto('/');
				return;
			}
			applyError = 'Service did not come back within 30 seconds. Try refreshing the page.';
		} catch (e) {
			applyError = e instanceof Error ? e.message : String(e);
		} finally {
			applying = false;
		}
	}
</script>

<div class="wizard">
	<header>
		<h1>Riglet Setup</h1>
		<nav class="steps">
			{#each STEPS as label, i}
				<button
					class="step-pill"
					class:active={i === step}
					class:done={i < step}
					onclick={() => { step = i; }}
				>
					<span class="step-num">{i + 1}</span>
					{label}
				</button>
			{/each}
		</nav>
	</header>

	<main>
		{#if step === 0}
			<StepWelcome hostname={config.network.hostname} onUpdate={updateHostname} />
		{:else if step === 1}
			<StepDetectRadios radios={config.radios} onUpdate={updateRadios} />
		{:else if step === 2}
			<StepMapAudio radios={config.radios} onUpdate={updateRadios} />
		{:else if step === 3}
			<StepPttMethod radios={config.radios} onUpdate={updateRadios} />
		{:else if step === 4}
			<StepReviewApply {config} onApply={applyAndStart} {applying} {applyError} />
		{/if}
	</main>

	<footer>
		<button onclick={prev} disabled={step === 0}>Back</button>
		{#if step < STEPS.length - 1}
			<button class="primary" onclick={next}>Next</button>
		{/if}
	</footer>
</div>

<style>
	:global(body) {
		margin: 0;
		background: #111;
		color: #e0e0e0;
		font-family: system-ui, sans-serif;
	}

	.wizard {
		min-height: 100vh;
		display: flex;
		flex-direction: column;
	}

	header {
		padding: 16px 24px;
		border-bottom: 1px solid #333;
		background: #1a1a1a;
	}

	h1 {
		margin: 0 0 16px;
		font-size: 1.4rem;
		color: #4a9eff;
	}

	.steps {
		display: flex;
		gap: 4px;
		flex-wrap: wrap;
	}

	.step-pill {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 6px 12px;
		border: 1px solid #444;
		border-radius: 20px;
		background: #111;
		color: #888;
		cursor: pointer;
		font-size: 0.85rem;
		transition: all 0.15s;
	}

	.step-pill.active {
		border-color: #4a9eff;
		color: #4a9eff;
		background: rgba(74, 158, 255, 0.1);
	}

	.step-pill.done {
		border-color: #4caf50;
		color: #4caf50;
		background: rgba(76, 175, 80, 0.08);
	}

	.step-num {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 20px;
		height: 20px;
		border-radius: 50%;
		background: #333;
		font-size: 0.75rem;
		font-weight: 700;
	}

	.step-pill.active .step-num { background: #4a9eff; color: #fff; }
	.step-pill.done .step-num { background: #4caf50; color: #fff; }

	main {
		flex: 1;
		padding: 32px 24px;
		max-width: 800px;
		width: 100%;
		box-sizing: border-box;
		margin: 0 auto;
	}

	footer {
		padding: 16px 24px;
		border-top: 1px solid #333;
		background: #1a1a1a;
		display: flex;
		gap: 12px;
		justify-content: flex-end;
	}

	button {
		padding: 8px 20px;
		border: 1px solid #555;
		border-radius: 4px;
		background: #2a2a2a;
		color: inherit;
		font-size: 0.95rem;
		cursor: pointer;
		transition: background 0.15s;
	}

	button:hover:not(:disabled) { background: #333; }
	button:disabled { opacity: 0.4; cursor: not-allowed; }

	button.primary {
		background: #4a9eff;
		border-color: #4a9eff;
		color: #fff;
		font-weight: 600;
	}

	button.primary:hover:not(:disabled) { background: #2a7ee0; }
</style>
