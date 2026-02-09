<script lang="ts">
	import { browseStore } from '$lib/stores.svelte';
	import { fetchNode } from '$lib/api';
	import type { TreeNode } from '$lib/types';

	interface Crumb {
		id: string;
		title: string;
	}

	let crumbs = $derived.by(() => {
		if (!browseStore.tree || !browseStore.selectedNodeId) return [];
		const path: Crumb[] = [];
		findPath(browseStore.tree, browseStore.selectedNodeId, path);
		return path;
	});

	function findPath(node: TreeNode, targetId: string, path: Crumb[]): boolean {
		path.push({ id: node.id, title: node.metadata.title || node.id });
		if (node.id === targetId) return true;
		if (node.children) {
			for (const child of node.children) {
				if (findPath(child, targetId, path)) return true;
			}
		}
		path.pop();
		return false;
	}

	async function navigate(id: string) {
		browseStore.setSelectedNode(id);
		browseStore.setLoading(true);
		try {
			const full = await fetchNode(browseStore.selectedDocument!, id);
			browseStore.setNodeContent(full.content);
		} catch (e) {
			browseStore.setError(e instanceof Error ? e.message : 'Failed to load node');
		} finally {
			browseStore.setLoading(false);
		}
	}
</script>

{#if crumbs.length > 1}
	<nav class="breadcrumb" aria-label="Breadcrumb">
		<ol>
			{#each crumbs as crumb, i}
				<li>
					{#if i < crumbs.length - 1}
						<button class="crumb-link" onclick={() => navigate(crumb.id)}>
							{crumb.title}
						</button>
						<span class="separator" aria-hidden="true">/</span>
					{:else}
						<span class="crumb-current" aria-current="page">{crumb.title}</span>
					{/if}
				</li>
			{/each}
		</ol>
	</nav>
{/if}

<style>
	.breadcrumb ol {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-1);
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.breadcrumb li {
		display: flex;
		align-items: center;
		gap: var(--space-1);
	}

	.crumb-link {
		font-size: var(--text-sm);
		color: var(--color-link);
		min-height: unset;
		min-width: unset;
		padding: var(--space-1);
		border-radius: var(--radius-sm);
		transition: color var(--transition-fast);
	}

	.crumb-link:hover {
		color: var(--color-link-hover);
		background: var(--color-bg-muted);
	}

	.separator {
		color: var(--color-text-muted);
		font-size: var(--text-sm);
	}

	.crumb-current {
		font-size: var(--text-sm);
		font-weight: var(--weight-semibold);
		color: var(--color-text);
		padding: var(--space-1);
	}
</style>
