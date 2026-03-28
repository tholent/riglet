<script lang="ts">
	import { onMount } from 'svelte';
	import favicon from '$lib/assets/favicon.svg';
	import { initTheme, getTheme } from '$lib/theme.js';
	import { theme } from '$lib/stores.js';
	import '../app.css';

	let { children } = $props();

	onMount(() => {
		initTheme();
		theme.set(getTheme());
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

{@render children()}
