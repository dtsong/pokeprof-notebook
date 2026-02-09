<script lang="ts">
	import { queryStore } from '$lib/stores.svelte';
	import type { Persona } from '$lib/types';

	const personas: { value: Persona; label: string }[] = [
		{ value: 'judge', label: 'Judge' },
		{ value: 'professor', label: 'Professor' },
		{ value: 'player', label: 'Player' }
	];
</script>

<div class="persona-toggle" role="radiogroup" aria-label="Response persona">
	{#each personas as p}
		<button
			type="button"
			role="radio"
			aria-checked={queryStore.persona === p.value}
			class="persona-btn"
			class:active={queryStore.persona === p.value}
			class:judge={p.value === 'judge'}
			class:professor={p.value === 'professor'}
			class:player={p.value === 'player'}
			onclick={() => queryStore.setPersona(p.value)}
		>
			{p.label}
		</button>
	{/each}
</div>

<style>
	.persona-toggle {
		display: flex;
		gap: var(--space-2);
	}

	.persona-btn {
		padding: var(--space-2) var(--space-4);
		border-radius: var(--radius-full);
		font-size: var(--text-sm);
		font-weight: var(--weight-medium);
		background: var(--color-bg-muted);
		color: var(--color-text-secondary);
		transition: all var(--transition-fast);
	}

	.persona-btn:hover {
		background: var(--color-border);
	}

	.persona-btn.active.judge {
		background: rgba(30, 58, 95, 0.15);
		color: var(--persona-judge);
	}

	.persona-btn.active.professor {
		background: rgba(26, 107, 60, 0.15);
		color: var(--persona-professor);
	}

	.persona-btn.active.player {
		background: rgba(184, 134, 11, 0.15);
		color: var(--persona-player);
	}
</style>
