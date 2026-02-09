<script lang="ts">
	import { queryStore } from '$lib/stores.svelte';

	function formatDocName(name: string): string {
		return name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
	}
</script>

{#if queryStore.route}
	<div class="badges-group">
		<span class="label">Sources:</span>
		<div class="badges">
			{#each queryStore.route.documents as doc}
				<span class="badge">{formatDocName(doc)}</span>
			{/each}
		</div>
	</div>
{/if}

{#if queryStore.sections.length > 0}
	<div class="badges-group">
		<span class="label">Sections:</span>
		<div class="badges">
			{#each queryStore.sections as section}
				<span class="badge" title="Score: {section.score}">
					{#if section.section_number}
						<span class="section-num">{section.section_number}</span>
					{/if}
					{section.title}
				</span>
			{/each}
		</div>
	</div>
{/if}

<style>
	.badges-group {
		display: flex;
		align-items: baseline;
		gap: var(--space-2);
		flex-wrap: wrap;
	}

	.label {
		font-size: var(--text-xs);
		font-weight: var(--weight-semibold);
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		flex-shrink: 0;
	}

	.badges {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1);
	}

	.badge {
		display: inline-flex;
		align-items: center;
		gap: var(--space-1);
		padding: var(--space-1) var(--space-3);
		font-size: var(--text-xs);
		font-weight: var(--weight-medium);
		border-radius: var(--radius-full);
		background: var(--badge-bg);
		color: var(--badge-text);
		white-space: nowrap;
	}

	.section-num {
		font-family: var(--font-mono);
		font-weight: var(--weight-semibold);
		color: var(--color-primary);
	}
</style>
