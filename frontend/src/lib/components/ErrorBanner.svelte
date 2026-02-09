<script lang="ts">
	import { queryStore } from '$lib/stores.svelte';
</script>

{#if queryStore.error}
	<div class="error-banner" role="alert">
		<svg class="error-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
			<circle cx="12" cy="12" r="10" />
			<line x1="12" y1="8" x2="12" y2="12" />
			<line x1="12" y1="16" x2="12.01" y2="16" />
		</svg>
		<p>{queryStore.error}</p>
		<button class="dismiss" onclick={() => queryStore.reset()} aria-label="Dismiss error">
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
				<line x1="18" y1="6" x2="6" y2="18" />
				<line x1="6" y1="6" x2="18" y2="18" />
			</svg>
		</button>
	</div>
{/if}

<style>
	.error-banner {
		display: flex;
		align-items: center;
		gap: var(--space-3);
		padding: var(--space-3) var(--space-4);
		background: var(--color-error-subtle);
		border: 1px solid var(--color-error);
		border-radius: var(--radius-md);
		color: var(--color-error);
		font-size: var(--text-sm);
	}

	.error-icon {
		width: 20px;
		height: 20px;
		flex-shrink: 0;
	}

	p {
		flex: 1;
		margin: 0;
	}

	.dismiss {
		flex-shrink: 0;
		min-height: 32px;
		min-width: 32px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--radius-sm);
		opacity: 0.7;
	}

	.dismiss:hover {
		opacity: 1;
		background: rgba(204, 0, 0, 0.1);
	}
</style>
