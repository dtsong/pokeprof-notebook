<script lang="ts">
	import { queryStore } from '$lib/stores.svelte';
	import { submitQuery, cancelQuery } from '$lib/api';

	let input = $state('');
	const isSearching = $derived(
		queryStore.stage !== 'idle' && queryStore.stage !== 'done' && queryStore.stage !== 'error'
	);

	function handleSubmit(e: Event) {
		e.preventDefault();
		const q = input.trim();
		if (!q) return;
		submitQuery(q, queryStore.persona);
	}

	function handleCancel() {
		cancelQuery();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && isSearching) {
			handleCancel();
		}
	}
</script>

<form class="search-bar" onsubmit={handleSubmit}>
	<input
		type="search"
		bind:value={input}
		placeholder="Ask a Pokémon TCG rules question..."
		disabled={isSearching}
		onkeydown={handleKeydown}
		aria-label="Search query"
	/>
	{#if isSearching}
		<button type="button" class="btn btn--cancel" onclick={handleCancel}>
			Cancel
		</button>
	{:else}
		<button type="submit" class="btn btn--primary" disabled={!input.trim()}>
			Ask
		</button>
	{/if}
</form>

<style>
	.search-bar {
		display: flex;
		gap: var(--space-2);
	}

	input {
		flex: 1;
		min-width: 0;
	}

	.btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: var(--space-3) var(--space-5);
		border-radius: var(--radius-md);
		font-weight: var(--weight-semibold);
		font-size: var(--text-sm);
		transition: all var(--transition-fast);
		white-space: nowrap;
	}

	.btn--primary {
		background: var(--color-primary);
		color: var(--color-primary-text);
	}

	.btn--primary:hover:not(:disabled) {
		background: var(--color-primary-hover);
	}

	.btn--primary:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.btn--cancel {
		background: var(--color-bg-muted);
		color: var(--color-text-secondary);
	}

	.btn--cancel:hover {
		background: var(--color-border);
	}
</style>
