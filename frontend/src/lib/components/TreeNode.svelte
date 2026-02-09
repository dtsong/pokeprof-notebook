<script lang="ts">
	import { browseStore } from '$lib/stores.svelte';
	import { fetchNode } from '$lib/api';
	import type { TreeNode } from '$lib/types';
	import TreeNodeSelf from './TreeNode.svelte';

	let { node, depth = 0 }: { node: TreeNode; depth?: number } = $props();

	const initiallyExpanded = depth < 1;
	let expanded = $state(initiallyExpanded);
	let hasChildren = $derived(node.children && node.children.length > 0);
	let isSelected = $derived(browseStore.selectedNodeId === node.id);

	function toggle() {
		if (hasChildren) {
			expanded = !expanded;
		}
	}

	async function select() {
		browseStore.setSelectedNode(node.id);
		browseStore.setLoading(true);
		try {
			const full = await fetchNode(browseStore.selectedDocument!, node.id);
			browseStore.setNodeContent(full.content);
		} catch (e) {
			browseStore.setError(e instanceof Error ? e.message : 'Failed to load node');
		} finally {
			browseStore.setLoading(false);
		}
	}
</script>

<li class="tree-node" style="--depth: {depth}">
	<div class="node-row" class:selected={isSelected}>
		<button
			class="toggle"
			onclick={toggle}
			aria-label={hasChildren ? (expanded ? 'Collapse' : 'Expand') : undefined}
			disabled={!hasChildren}
		>
			{#if hasChildren}
				<svg class="chevron" class:open={expanded} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<polyline points="9 18 15 12 9 6" />
				</svg>
			{:else}
				<span class="leaf-spacer"></span>
			{/if}
		</button>

		<button class="node-label" onclick={select} title={node.metadata.title}>
			<span class="node-title truncate">
				{#if node.metadata.section_number}
					<span class="section-num">{node.metadata.section_number}</span>
				{/if}
				{node.metadata.title || node.id}
			</span>
			<span class="node-tokens text-xs text-muted">{node.token_count}</span>
		</button>
	</div>

	{#if expanded && hasChildren}
		<ul class="children" role="group">
			{#each node.children as child (child.id)}
				<TreeNodeSelf node={child} depth={depth + 1} />
			{/each}
		</ul>
	{/if}
</li>

<style>
	.tree-node {
		list-style: none;
	}

	.node-row {
		display: flex;
		align-items: center;
		padding-left: calc(var(--depth) * var(--space-4));
		border-radius: var(--radius-sm);
		transition: background var(--transition-fast);
	}

	.node-row:hover {
		background: var(--color-bg-muted);
	}

	.node-row.selected {
		background: var(--color-accent-subtle);
	}

	.toggle {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 24px;
		height: 24px;
		min-height: unset;
		min-width: unset;
		flex-shrink: 0;
		padding: 0;
	}

	.toggle:disabled {
		cursor: default;
	}

	.chevron {
		width: 14px;
		height: 14px;
		transition: transform var(--transition-fast);
		color: var(--color-text-muted);
	}

	.chevron.open {
		transform: rotate(90deg);
	}

	.leaf-spacer {
		display: inline-block;
		width: 14px;
	}

	.node-label {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-2);
		flex: 1;
		min-width: 0;
		min-height: 32px;
		padding: var(--space-1) var(--space-2);
		text-align: left;
		font-size: var(--text-sm);
		border-radius: var(--radius-sm);
	}

	.node-title {
		min-width: 0;
	}

	.section-num {
		color: var(--color-text-muted);
		font-family: var(--font-mono);
		font-size: var(--text-xs);
		margin-right: var(--space-1);
	}

	.node-tokens {
		flex-shrink: 0;
		font-family: var(--font-mono);
	}

	.children {
		padding: 0;
		margin: 0;
	}
</style>
