<script lang="ts">
	import { recentStore, queryStore } from '$lib/stores.svelte';
	import { submitQuery } from '$lib/api';

	function handleClick(query: string, persona: string) {
		queryStore.setPersona(persona as 'judge' | 'professor' | 'player');
		submitQuery(query, persona as 'judge' | 'professor' | 'player');
	}

	function timeAgo(ts: number): string {
		const diff = Date.now() - ts;
		const mins = Math.floor(diff / 60000);
		if (mins < 1) return 'just now';
		if (mins < 60) return `${mins}m ago`;
		const hrs = Math.floor(mins / 60);
		if (hrs < 24) return `${hrs}h ago`;
		const days = Math.floor(hrs / 24);
		return `${days}d ago`;
	}
</script>

{#if recentStore.items.length > 0}
	<div class="recent">
		<div class="recent-header">
			<h3>Recent</h3>
			<button class="clear-btn" onclick={() => recentStore.clear()}>Clear</button>
		</div>
		<ul class="recent-list">
			{#each recentStore.items.slice(0, 5) as item}
				<li>
					<button class="recent-item" onclick={() => handleClick(item.query, item.persona)}>
						<span class="recent-query">{item.query}</span>
						<span class="recent-meta">
							<span class="badge badge--{item.persona}">{item.persona}</span>
							<span class="recent-time">{timeAgo(item.timestamp)}</span>
						</span>
					</button>
				</li>
			{/each}
		</ul>
	</div>
{/if}

<style>
	.recent {
		margin-top: var(--space-6);
	}

	.recent-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: var(--space-3);
	}

	h3 {
		font-size: var(--text-sm);
		font-weight: var(--weight-semibold);
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.clear-btn {
		font-size: var(--text-xs);
		color: var(--color-text-muted);
		min-height: 32px;
		min-width: auto;
		padding: var(--space-1) var(--space-2);
	}

	.clear-btn:hover {
		color: var(--color-text-secondary);
	}

	.recent-list {
		list-style: none;
		padding: 0;
	}

	.recent-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-3);
		width: 100%;
		padding: var(--space-3);
		border-radius: var(--radius-md);
		text-align: left;
		min-height: var(--touch-min);
		transition: background var(--transition-fast);
	}

	.recent-item:hover {
		background: var(--color-bg-muted);
	}

	.recent-query {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: var(--text-sm);
	}

	.recent-meta {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		flex-shrink: 0;
	}

	.recent-time {
		font-size: var(--text-xs);
		color: var(--color-text-muted);
	}
</style>
