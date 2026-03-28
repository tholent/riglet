<script lang="ts">
	import { onMount } from 'svelte';
	import type { LayoutConfig } from '$lib/layout/types.js';
	import {
		activeLayout,
		listLayouts,
		loadLayout,
		saveLayout,
		deleteLayout,
		exportLayout,
		importLayout,
	} from '$lib/layout/store.js';
	import { DEFAULT_LAYOUT_IDS } from '$lib/layout/defaults.js';

	// Whether the dropdown panel is open.
	let open = $state(false);

	// All available layouts (defaults + custom). Refreshed on open.
	let layouts = $state<LayoutConfig[]>([]);

	// Current active layout from store.
	let current = $state<LayoutConfig>($activeLayout);
	$effect(() => {
		current = $activeLayout;
	});

	// Inline rename state: tracks which layout id is being renamed.
	let renamingId = $state<string | null>(null);
	let renameValue = $state('');

	// Confirmation dialog for delete.
	let confirmDeleteId = $state<string | null>(null);

	// Error / status message shown briefly.
	let statusMsg = $state('');
	let statusTimer: ReturnType<typeof setTimeout> | null = null;

	function showStatus(msg: string): void {
		statusMsg = msg;
		if (statusTimer !== null) clearTimeout(statusTimer);
		statusTimer = setTimeout(() => {
			statusMsg = '';
		}, 2500);
	}

	function refreshLayouts(): void {
		layouts = listLayouts();
	}

	function toggleOpen(): void {
		open = !open;
		if (open) refreshLayouts();
	}

	function handleSelect(id: string): void {
		loadLayout(id);
		open = false;
		showStatus('Layout loaded');
	}

	function handleSaveCurrent(): void {
		// Persist the currently active layout (overwrites or adds if custom).
		saveLayout(current);
		showStatus('Layout saved');
		refreshLayouts();
	}

	function handleSaveAsNew(): void {
		const name = prompt('Enter a name for the new layout:', current.name + ' copy');
		if (!name) return;
		const newLayout: LayoutConfig = {
			...current,
			id: `custom-${Date.now()}`,
			name,
		};
		saveLayout(newLayout);
		loadLayout(newLayout.id);
		showStatus(`Saved as "${name}"`);
		refreshLayouts();
	}

	function handleStartRename(layout: LayoutConfig): void {
		renamingId = layout.id;
		renameValue = layout.name;
	}

	function handleCommitRename(layout: LayoutConfig): void {
		if (!renameValue.trim()) {
			renamingId = null;
			return;
		}
		const renamed: LayoutConfig = { ...layout, name: renameValue.trim() };
		saveLayout(renamed);
		// If this was the active layout, reload it so the name updates.
		if (current.id === layout.id) {
			loadLayout(renamed.id);
		}
		renamingId = null;
		refreshLayouts();
		showStatus('Renamed');
	}

	function handleCancelRename(): void {
		renamingId = null;
	}

	function handleDeleteRequest(id: string): void {
		confirmDeleteId = id;
	}

	function handleDeleteConfirm(): void {
		if (confirmDeleteId === null) return;
		try {
			deleteLayout(confirmDeleteId);
			showStatus('Layout deleted');
		} catch (e) {
			showStatus((e as Error).message);
		}
		confirmDeleteId = null;
		refreshLayouts();
	}

	function handleDeleteCancel(): void {
		confirmDeleteId = null;
	}

	function handleExport(layout: LayoutConfig): void {
		const json = exportLayout(layout);
		const blob = new Blob([json], { type: 'application/json' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `riglet-layout-${layout.id}.json`;
		a.click();
		URL.revokeObjectURL(url);
		showStatus(`Exported "${layout.name}"`);
	}

	// File input element — programmatically clicked for import.
	let fileInput = $state<HTMLInputElement | undefined>(undefined);

	function handleImportClick(): void {
		if (!fileInput) return;
		fileInput.value = '';
		fileInput.click();
	}

	function handleFileChange(event: Event): void {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;

		const reader = new FileReader();
		reader.onload = () => {
			try {
				const layout = importLayout(reader.result as string);
				loadLayout(layout.id);
				refreshLayouts();
				showStatus(`Imported "${layout.name}"`);
			} catch (e) {
				showStatus(`Import failed: ${(e as Error).message}`);
			}
		};
		reader.readAsText(file);
	}

	// Close panel when clicking outside.
	function handleDocumentClick(e: MouseEvent): void {
		const target = e.target as Node;
		if (!container?.contains(target)) {
			open = false;
		}
	}

	let container: HTMLDivElement | undefined;

	onMount(() => {
		document.addEventListener('click', handleDocumentClick);
		return () => {
			document.removeEventListener('click', handleDocumentClick);
			if (statusTimer !== null) clearTimeout(statusTimer);
		};
	});

	function isDefault(id: string): boolean {
		return DEFAULT_LAYOUT_IDS.has(id);
	}

	function focusOnMount(node: HTMLElement): void {
		node.focus();
	}
</script>

<div class="layout-manager" bind:this={container}>
	<!-- Toolbar button -->
	<button
		class="layout-btn"
		class:active={open}
		onclick={toggleOpen}
		aria-expanded={open}
		aria-haspopup="true"
		aria-label="Layout manager"
		title="Manage layouts"
	>
		<svg
			width="16"
			height="16"
			viewBox="0 0 16 16"
			fill="currentColor"
			aria-hidden="true"
			focusable="false"
		>
			<!-- Grid/layout icon -->
			<rect x="1" y="1" width="6" height="6" rx="1" />
			<rect x="9" y="1" width="6" height="6" rx="1" />
			<rect x="1" y="9" width="6" height="6" rx="1" />
			<rect x="9" y="9" width="6" height="6" rx="1" />
		</svg>
		<span>Layouts</span>
	</button>

	{#if open}
		<div class="layout-panel" role="dialog" aria-label="Layout manager panel">
			<!-- Header actions -->
			<div class="panel-actions">
				<button class="action-btn" onclick={handleSaveCurrent} title="Save current layout">
					Save current
				</button>
				<button class="action-btn" onclick={handleSaveAsNew} title="Clone as new layout">
					Save as new
				</button>
				<button class="action-btn" onclick={handleImportClick} title="Import layout from file">
					Import
				</button>
				<!-- Hidden file input -->
				<input
					bind:this={fileInput}
					type="file"
					accept=".json,application/json"
					style="display:none"
					onchange={handleFileChange}
					aria-hidden="true"
				/>
			</div>

			{#if statusMsg}
				<div class="status-msg" role="status" aria-live="polite">{statusMsg}</div>
			{/if}

			<!-- Layout list -->
			<ul class="layout-list" role="listbox" aria-label="Available layouts">
				{#each layouts as layout (layout.id)}
					<li
						class="layout-item"
						class:selected={layout.id === current.id}
						role="option"
						aria-selected={layout.id === current.id}
					>
						{#if renamingId === layout.id}
							<!-- Inline rename form -->
							<input
								class="rename-input"
								type="text"
								bind:value={renameValue}
								onkeydown={(e) => {
									if (e.key === 'Enter') handleCommitRename(layout);
									if (e.key === 'Escape') handleCancelRename();
								}}
								aria-label="Rename layout"
								use:focusOnMount
							/>
							<button
								class="icon-btn ok"
								onclick={() => handleCommitRename(layout)}
								aria-label="Confirm rename"
								title="Confirm">✓</button
							>
							<button
								class="icon-btn cancel"
								onclick={handleCancelRename}
								aria-label="Cancel rename"
								title="Cancel">✕</button
							>
						{:else}
							<!-- Layout name + select button -->
							<button
								class="layout-name-btn"
								onclick={() => handleSelect(layout.id)}
								aria-label={`Load layout: ${layout.name}`}
							>
								{layout.name}
								{#if isDefault(layout.id)}
									<span class="default-badge">default</span>
								{/if}
							</button>

							<!-- Per-layout actions -->
							<div class="item-actions">
								<button
									class="icon-btn export"
									onclick={() => handleExport(layout)}
									aria-label={`Export ${layout.name}`}
									title="Export as JSON"
								>
									↓
								</button>
								{#if !isDefault(layout.id)}
									<button
										class="icon-btn rename"
										onclick={() => handleStartRename(layout)}
										aria-label={`Rename ${layout.name}`}
										title="Rename"
									>
										✎
									</button>
									<button
										class="icon-btn delete"
										onclick={() => handleDeleteRequest(layout.id)}
										aria-label={`Delete ${layout.name}`}
										title="Delete"
									>
										✕
									</button>
								{/if}
							</div>
						{/if}
					</li>
				{/each}
			</ul>
		</div>
	{/if}

	<!-- Delete confirmation dialog -->
	{#if confirmDeleteId !== null}
		<div class="confirm-overlay" role="dialog" aria-modal="true" aria-label="Confirm delete">
			<div class="confirm-dialog">
				<p>Delete this layout? This cannot be undone.</p>
				<div class="confirm-actions">
					<button class="action-btn danger" onclick={handleDeleteConfirm}>Delete</button>
					<button class="action-btn" onclick={handleDeleteCancel}>Cancel</button>
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.layout-manager {
		position: relative;
		display: inline-flex;
		align-items: center;
	}

	.layout-btn {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 5px 10px;
		background: #222;
		border: 1px solid #444;
		border-radius: 4px;
		color: #ccc;
		font-size: 0.8rem;
		cursor: pointer;
		transition: background 0.15s;
	}

	.layout-btn:hover,
	.layout-btn.active {
		background: #333;
		border-color: #4a9eff;
		color: #fff;
	}

	.layout-panel {
		position: absolute;
		top: calc(100% + 6px);
		right: 0;
		width: 280px;
		background: #1e1e1e;
		border: 1px solid #444;
		border-radius: 6px;
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
		z-index: 500;
		padding: 10px;
	}

	.panel-actions {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
		margin-bottom: 8px;
	}

	.action-btn {
		flex: 1;
		padding: 5px 8px;
		background: #2a2a2a;
		border: 1px solid #444;
		border-radius: 4px;
		color: #ccc;
		font-size: 0.75rem;
		cursor: pointer;
		white-space: nowrap;
	}

	.action-btn:hover {
		background: #333;
		color: #fff;
	}

	.action-btn.danger {
		border-color: #c0392b;
		color: #e74c3c;
	}

	.action-btn.danger:hover {
		background: #c0392b;
		color: #fff;
	}

	.status-msg {
		font-size: 0.75rem;
		color: #4a9eff;
		padding: 3px 0 6px;
		text-align: center;
	}

	.layout-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 2px;
		max-height: 280px;
		overflow-y: auto;
	}

	.layout-item {
		display: flex;
		align-items: center;
		gap: 4px;
		padding: 4px 6px;
		border-radius: 4px;
		border: 1px solid transparent;
	}

	.layout-item.selected {
		border-color: #4a9eff;
		background: rgba(74, 158, 255, 0.08);
	}

	.layout-name-btn {
		flex: 1;
		display: flex;
		align-items: center;
		gap: 6px;
		background: none;
		border: none;
		color: #e0e0e0;
		font-size: 0.85rem;
		cursor: pointer;
		text-align: left;
		padding: 2px 4px;
		border-radius: 3px;
	}

	.layout-name-btn:hover {
		color: #fff;
		background: rgba(255, 255, 255, 0.05);
	}

	.default-badge {
		font-size: 0.65rem;
		background: #2a4a6e;
		color: #7ab8ff;
		border-radius: 3px;
		padding: 1px 4px;
		flex-shrink: 0;
	}

	.item-actions {
		display: flex;
		gap: 2px;
		flex-shrink: 0;
	}

	.icon-btn {
		width: 22px;
		height: 22px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		background: none;
		border: 1px solid transparent;
		border-radius: 3px;
		color: #888;
		font-size: 0.8rem;
		cursor: pointer;
		padding: 0;
	}

	.icon-btn:hover {
		border-color: #555;
		color: #ccc;
	}

	.icon-btn.delete:hover {
		border-color: #c0392b;
		color: #e74c3c;
	}

	.icon-btn.ok:hover {
		border-color: #27ae60;
		color: #2ecc71;
	}

	.rename-input {
		flex: 1;
		background: #111;
		border: 1px solid #4a9eff;
		border-radius: 3px;
		color: #e0e0e0;
		font-size: 0.82rem;
		padding: 2px 6px;
		outline: none;
	}

	/* Delete confirmation overlay */
	.confirm-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
	}

	.confirm-dialog {
		background: #1e1e1e;
		border: 1px solid #555;
		border-radius: 8px;
		padding: 20px 24px;
		min-width: 260px;
		text-align: center;
	}

	.confirm-dialog p {
		color: #ccc;
		margin: 0 0 16px;
		font-size: 0.9rem;
	}

	.confirm-actions {
		display: flex;
		gap: 10px;
		justify-content: center;
	}
</style>
