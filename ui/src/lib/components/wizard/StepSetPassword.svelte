<script lang="ts">
	import { onMount } from 'svelte';
	import { getAuthStatus, postSetPassword } from '$lib/api.js';

	let { onPasswordSet }: { onPasswordSet: () => void } = $props();

	let password = $state('');
	let confirm = $state('');
	let error = $state<string | null>(null);
	let loading = $state(false);
	let alreadySet = $state(false);

	onMount(async () => {
		try {
			const auth = await getAuthStatus();
			if (auth.password_set) {
				alreadySet = true;
			}
		} catch {
			// ignore
		}
	});

	async function handleSubmit(e: Event) {
		e.preventDefault();
		error = null;

		if (password.length < 8) {
			error = 'Password must be at least 8 characters.';
			return;
		}
		if (password !== confirm) {
			error = 'Passwords do not match.';
			return;
		}

		loading = true;
		try {
			await postSetPassword(password);
			onPasswordSet();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to set password.';
		} finally {
			loading = false;
		}
	}
</script>

<div class="step">
	<h2>Set Password</h2>
	<p class="description">
		Protect your Riglet instance with a password. You will be prompted to log in on each new session.
	</p>

	{#if alreadySet}
		<div class="already-set">
			<span class="check">✓</span>
			<span>Password already configured.</span>
		</div>
		<button class="primary" onclick={() => onPasswordSet()}>Continue</button>
	{:else}
		<form onsubmit={handleSubmit}>
			<div class="field">
				<label for="sp-password">Password</label>
				<input
					id="sp-password"
					type="password"
					bind:value={password}
					autocomplete="new-password"
					disabled={loading}
					minlength={8}
					required
				/>
			</div>

			<div class="field">
				<label for="sp-confirm">Confirm Password</label>
				<input
					id="sp-confirm"
					type="password"
					bind:value={confirm}
					autocomplete="new-password"
					disabled={loading}
					required
				/>
			</div>

			{#if error}
				<p class="error" role="alert">{error}</p>
			{/if}

			<button type="submit" class="primary" disabled={loading}>
				{loading ? 'Setting password...' : 'Set Password & Finish'}
			</button>
		</form>

		<p class="skip-note">
			<button class="link" onclick={() => onPasswordSet()} disabled={loading}>
				Skip for now (no password protection)
			</button>
		</p>
	{/if}
</div>

<style>
	.step {
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	h2 {
		margin: 0;
		color: #4a9eff;
		font-size: 1.2rem;
	}

	.description {
		margin: 0;
		color: #aaa;
		font-size: 0.9rem;
		line-height: 1.5;
	}

	form {
		display: flex;
		flex-direction: column;
		gap: 16px;
		max-width: 400px;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	label {
		font-size: 0.85rem;
		color: #aaa;
		font-weight: 500;
	}

	input {
		padding: 10px 12px;
		background: #111;
		border: 1px solid #444;
		border-radius: 4px;
		color: #e0e0e0;
		font-size: 1rem;
		outline: none;
		transition: border-color 0.15s;
	}

	input:focus {
		border-color: #4a9eff;
	}

	input:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.error {
		margin: 0;
		padding: 8px 12px;
		background: rgba(220, 53, 69, 0.15);
		border: 1px solid rgba(220, 53, 69, 0.4);
		border-radius: 4px;
		color: #f87171;
		font-size: 0.875rem;
	}

	button.primary {
		padding: 10px 20px;
		background: #4a9eff;
		border: 1px solid #4a9eff;
		border-radius: 4px;
		color: #fff;
		font-size: 1rem;
		font-weight: 600;
		cursor: pointer;
		transition: background 0.15s;
		align-self: flex-start;
	}

	button.primary:hover:not(:disabled) {
		background: #2a7ee0;
	}

	button.primary:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.already-set {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 12px 16px;
		background: rgba(76, 175, 80, 0.1);
		border: 1px solid rgba(76, 175, 80, 0.4);
		border-radius: 4px;
		color: #4caf50;
		font-size: 0.95rem;
	}

	.check {
		font-size: 1.2rem;
	}

	.skip-note {
		margin: 0;
	}

	button.link {
		background: none;
		border: none;
		color: #666;
		font-size: 0.85rem;
		cursor: pointer;
		padding: 0;
		text-decoration: underline;
	}

	button.link:hover:not(:disabled) {
		color: #aaa;
	}

	button.link:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
</style>
