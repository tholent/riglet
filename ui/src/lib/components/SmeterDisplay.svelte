<script lang="ts">
	interface Props {
		smeter: number; // S-units (0-9 = S0-S9, 10-16 = S9+10 through S9+60)
	}
	let { smeter = 0 }: Props = $props();

	const S_LABELS = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8', 'S9', '+10', '+20', '+30', '+40', '+50', '+60'];
	const BAR_COUNT = S_LABELS.length;

	function barColor(index: number): string {
		if (index >= 9) return '#f44336'; // S9+ -> red
		if (index >= 6) return '#ff9800'; // S6-S8 -> orange
		return '#4caf50';                  // S1-S5 -> green
	}
</script>

<div class="smeter">
	<div class="bars">
		{#each S_LABELS as label, i}
			<div class="bar-col">
				<div
					class="bar"
					class:lit={i < smeter}
					style:background={i < smeter ? barColor(i) : '#1a1a1a'}
				></div>
				<span class="bar-label">{label}</span>
			</div>
		{/each}
	</div>
	<div class="reading">
		{smeter >= 9
			? `S9 +${(smeter - 9) * 10} dB`
			: smeter > 0
				? `S${smeter}`
				: 'S0'}
	</div>
</div>

<style>
	.smeter {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.bars {
		display: flex;
		align-items: flex-end;
		gap: 3px;
		height: 48px;
	}

	.bar-col {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2px;
		flex: 1;
	}

	.bar {
		width: 100%;
		height: 36px;
		border-radius: 2px;
		transition: background 0.05s;
	}

	.bar-label {
		font-size: 0.6rem;
		color: #666;
		white-space: nowrap;
	}

	.reading {
		font-family: 'Courier New', monospace;
		font-size: 0.9rem;
		color: #4caf50;
		text-align: right;
		padding-right: 4px;
	}
</style>
