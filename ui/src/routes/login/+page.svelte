<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { getAuthStatus, postLogin } from '$lib/api.js';

	let password = $state('');
	let error = $state<string | null>(null);
	let loading = $state(false);
	let passwordInput: HTMLInputElement | undefined = $state();

	onMount(async () => {
		try {
			const auth = await getAuthStatus();
			if (auth.authenticated) {
				await goto('/');
				return;
			}
			if (!auth.password_set) {
				await goto('/setup');
				return;
			}
		} catch {
			// backend unreachable — stay on login page
		}
		passwordInput?.focus();
	});

	async function handleSubmit(e: Event) {
		e.preventDefault();
		if (loading) return;
		error = null;
		loading = true;
		try {
			await postLogin(password);
			await goto('/');
		} catch {
			error = 'Invalid password. Please try again.';
			password = '';
			passwordInput?.focus();
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head>
	<title>Riglet — Log In</title>
</svelte:head>

<div class="page">
	<div class="card">
		<h1 class="brand">Riglet</h1>
		<p class="subtitle">Enter your password to continue</p>

		<form onsubmit={handleSubmit}>
			<div class="field">
				<label for="password">Password</label>
				<input
					id="password"
					type="password"
					bind:value={password}
					bind:this={passwordInput}
					autocomplete="current-password"
					disabled={loading}
					required
				/>
			</div>

			{#if error}
				<p class="error" role="alert">{error}</p>
			{/if}

			<button type="submit" class="primary" disabled={loading}>
				{loading ? 'Logging in...' : 'Log In'}
			</button>
		</form>
	</div>
</div>

<style>
	:global(body) {
		margin: 0;
		background: #111;
		color: #e0e0e0;
		font-family: system-ui, sans-serif;
	}

	.page {
		min-height: 100vh;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 24px;
		box-sizing: border-box;
	}

	.card {
		background: #1a1a1a;
		border: 1px solid #333;
		border-radius: 8px;
		padding: 40px 36px;
		width: 100%;
		max-width: 360px;
		box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
	}

	.brand {
		margin: 0 0 8px;
		font-size: 1.8rem;
		font-weight: 700;
		color: #4a9eff;
		text-align: center;
	}

	.subtitle {
		margin: 0 0 28px;
		color: #888;
		font-size: 0.9rem;
		text-align: center;
	}

	form {
		display: flex;
		flex-direction: column;
		gap: 16px;
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
	}

	button.primary:hover:not(:disabled) {
		background: #2a7ee0;
	}

	button.primary:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
</style>
