<script lang="ts">
	import { browseStore } from '$lib/stores.svelte';
	import TreeNode from './TreeNode.svelte';
</script>

{#if browseStore.tree}
	<nav class="tree-nav" aria-label="Document tree">
		<ul class="tree-root" role="tree">
			{#each browseStore.tree.children as child (child.id)}
				<TreeNode node={child} depth={0} />
			{/each}
		</ul>
	</nav>
{/if}

<style>
	.tree-nav {
		overflow-y: auto;
		overflow-x: hidden;
		padding: var(--space-2);
	}

	.tree-root {
		padding: 0;
		margin: 0;
		list-style: none;
	}
</style>
