<script lang="ts">
	interface Props {
		swr: number;
		ptt: boolean;
	}
	let { swr, ptt }: Props = $props();

	// Clamp SWR to display range 1.0 – 3.0+
	const MIN_SWR = 1.0;
	const MAX_SWR = 3.0;

	let fillPct = $derived(Math.min(((swr - MIN_SWR) / (MAX_SWR - MIN_SWR)) * 100, 100));

	let color = $derived(
		swr < 1.5 ? '#4caf50' : swr < 2.5 ? '#ffb300' : '#f44336',
	);

	let label = $derived(swr >= MAX_SWR ? `${MAX_SWR.toFixed(1)}+` : swr.toFixed(1));
</script>

{#if ptt}
	<div class="swr-meter" role="meter" aria-label={`SWR ${label}`} aria-valuenow={swr} aria-valuemin={1} aria-valuemax={3}>
		<span class="swr-title">SWR</span>
		<div class="bar-track">
			<div class="bar-fill" style="width: {fillPct}%; background: {color}"></div>
		</div>
		<span class="swr-value" style="color: {color}">{label}</span>
	</div>
{/if}

<style>
	.swr-meter {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.swr-title {
		font-size: 0.75rem;
		font-weight: 700;
		color: #888;
		letter-spacing: 0.05em;
		min-width: 28px;
	}

	.bar-track {
		flex: 1;
		height: 8px;
		background: #2a2a2a;
		border-radius: 4px;
		overflow: hidden;
		border: 1px solid #3a3a3a;
	}

	.bar-fill {
		height: 100%;
		border-radius: 4px;
		transition: width 0.1s ease-out, background 0.1s ease-out;
	}

	.swr-value {
		font-size: 0.8rem;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		min-width: 36px;
		text-align: right;
	}

	@media (prefers-reduced-motion: reduce) {
		.bar-fill {
			transition: none;
		}
	}
</style>
