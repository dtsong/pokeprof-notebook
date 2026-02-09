<script lang="ts">
	import DocumentSelector from '$lib/components/DocumentSelector.svelte';
	import TreeNavigator from '$lib/components/TreeNavigator.svelte';
	import ContentViewer from '$lib/components/ContentViewer.svelte';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import { browseStore } from '$lib/stores.svelte';
</script>

<svelte:head>
	<title>Browse — PokéProf Notebook</title>
</svelte:head>

<div class="page">
	<DocumentSelector />

	{#if browseStore.loading && !browseStore.tree}
		<p class="text-muted loading-msg">Loading tree...</p>
	{/if}

	{#if browseStore.tree}
		<div class="browse-layout">
			<div class="browse-tree">
				<TreeNavigator />
			</div>
			<div class="browse-content">
				{#if browseStore.nodeContent}
					<Breadcrumb />
					<ContentViewer content={browseStore.nodeContent} />
				{:else if browseStore.loading}
					<p class="text-muted">Loading...</p>
				{:else}
					<p class="text-muted">Select a node to view its content.</p>
				{/if}
			</div>
		</div>
	{/if}
</div>

<style>
	.loading-msg {
		padding: var(--space-4) 0;
	}

	.browse-layout {
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
		margin-top: var(--space-4);
	}

	.browse-tree {
		border: 1px solid var(--color-border);
		border-radius: var(--radius-md);
		background: var(--color-bg-elevated);
		max-height: 50vh;
		overflow-y: auto;
	}

	.browse-content {
		min-width: 0;
	}

	@media (min-width: 768px) {
		.browse-layout {
			flex-direction: row;
		}

		.browse-tree {
			width: 320px;
			min-width: 280px;
			max-height: calc(100vh - 160px);
			flex-shrink: 0;
		}

		.browse-content {
			flex: 1;
		}
	}
</style>
