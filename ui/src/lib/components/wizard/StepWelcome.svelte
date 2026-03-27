<script lang="ts">
	interface Props {
		hostname: string;
		onUpdate: (hostname: string) => void;
	}
	let { hostname, onUpdate }: Props = $props();
</script>

<div class="step-welcome">
	<h2>Welcome to Riglet</h2>
	<p>This wizard will help you configure your radio station. Let's start with the basics.</p>

	<div class="field">
		<label for="hostname">Hostname</label>
		<input
			id="hostname"
			type="text"
			value={hostname}
			oninput={(e) => onUpdate((e.target as HTMLInputElement).value)}
			placeholder="riglet"
		/>
		<small>Your device will be reachable at <code>{hostname || 'riglet'}.local</code></small>
	</div>
</div>

<style>
	.step-welcome {
		max-width: 480px;
	}

	h2 {
		margin-top: 0;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin-top: 24px;
	}

	label {
		font-weight: 600;
	}

	input {
		padding: 8px 10px;
		border: 1px solid #555;
		border-radius: 4px;
		background: #1a1a1a;
		color: inherit;
		font-size: 1rem;
	}

	small {
		color: #888;
	}
</style>
