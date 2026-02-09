<script lang="ts">
	import { browseStore } from '$lib/stores.svelte';
	import { fetchIndexes, fetchTree } from '$lib/api';

	let loading = $state(false);

	async function loadIndexes() {
		loading = true;
		try {
			const indexes = await fetchIndexes();
			browseStore.setIndexes(indexes);
		} catch (e) {
			browseStore.setError(e instanceof Error ? e.message : 'Failed to load indexes');
		} finally {
			loading = false;
		}
	}

	async function selectDocument(event: Event) {
		const target = event.target as HTMLSelectElement;
		const name = target.value;
		if (!name) {
			browseStore.setSelectedDocument(null);
			return;
		}
		browseStore.setSelectedDocument(name);
		browseStore.setLoading(true);
		try {
			const tree = await fetchTree(name);
			browseStore.setTree(tree);
		} catch (e) {
			browseStore.setError(e instanceof Error ? e.message : 'Failed to load tree');
		} finally {
			browseStore.setLoading(false);
		}
	}

	$effect(() => {
		loadIndexes();
	});
</script>

<div class="doc-selector">
	<label for="index-select" class="selector-label">Document</label>
	<select
		id="index-select"
		onchange={selectDocument}
		disabled={loading || browseStore.indexes.length === 0}
		value={browseStore.selectedDocument ?? ''}
	>
		<option value="">{loading ? 'Loading...' : 'Select a document'}</option>
		{#each browseStore.indexes as idx}
			<option value={idx.name}>
				{idx.name} ({idx.node_count} nodes, {idx.total_tokens.toLocaleString()} tokens)
			</option>
		{/each}
	</select>

	{#if browseStore.error}
		<p class="selector-error">{browseStore.error}</p>
	{/if}
</div>

<style>
	.doc-selector {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}

	.selector-label {
		font-size: var(--text-sm);
		font-weight: var(--weight-semibold);
		color: var(--color-text-secondary);
	}

	select {
		width: 100%;
	}

	.selector-error {
		font-size: var(--text-sm);
		color: var(--color-error);
	}
</style>
