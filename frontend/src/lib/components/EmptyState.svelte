<script lang="ts">
	let { title = 'Ask a question', message = 'Search for Pokémon TCG rules, card interactions, and rulings.' }: {
		title?: string;
		message?: string;
	} = $props();
</script>

<div class="empty-state">
	<svg class="empty-icon" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5">
		<circle cx="22" cy="22" r="16" />
		<line x1="33" y1="33" x2="42" y2="42" />
	</svg>
	<h2>{title}</h2>
	<p>{message}</p>
</div>

<style>
	.empty-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		text-align: center;
		padding: var(--space-12) var(--space-4);
		color: var(--color-text-muted);
	}

	.empty-icon {
		width: 64px;
		height: 64px;
		margin-bottom: var(--space-4);
		opacity: 0.4;
	}

	h2 {
		font-size: var(--text-xl);
		font-weight: var(--weight-semibold);
		color: var(--color-text-secondary);
		margin-bottom: var(--space-2);
	}

	p {
		font-size: var(--text-sm);
		max-width: 360px;
	}
</style>
