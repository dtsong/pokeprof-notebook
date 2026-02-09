<script lang="ts">
	import { marked } from 'marked';
	import { queryStore } from '$lib/stores.svelte';

	let { onShowProof }: { onShowProof?: () => void } = $props();

	const renderedHtml = $derived(
		queryStore.answer ? marked.parse(queryStore.answer) as string : ''
	);
</script>

{#if queryStore.answer || queryStore.stage === 'streaming'}
	<div class="answer-card">
		<div class="answer-header">
			<span class="persona-label badge badge--{queryStore.persona}">
				{queryStore.persona}
			</span>
			{#if queryStore.stage === 'streaming'}
				<span class="streaming-indicator">
					<span class="dot"></span>
					<span class="dot"></span>
					<span class="dot"></span>
				</span>
			{/if}
		</div>
		<div class="prose">
			{@html renderedHtml}
		</div>
		{#if queryStore.stage === 'done' && onShowProof}
			<div class="answer-actions">
				<button class="proof-btn" onclick={onShowProof}>
					Show as Proof
				</button>
			</div>
		{/if}
	</div>
{/if}

<style>
	.answer-card {
		background: var(--card-bg);
		border: 1px solid var(--card-border);
		border-radius: var(--radius-lg);
		padding: var(--space-5);
		box-shadow: var(--card-shadow);
	}

	.answer-header {
		display: flex;
		align-items: center;
		gap: var(--space-3);
		margin-bottom: var(--space-4);
	}

	.persona-label {
		text-transform: capitalize;
	}

	.streaming-indicator {
		display: flex;
		gap: 3px;
	}

	.dot {
		width: 4px;
		height: 4px;
		border-radius: 50%;
		background: var(--color-text-muted);
		animation: pulse 1.2s infinite;
	}

	.dot:nth-child(2) { animation-delay: 0.2s; }
	.dot:nth-child(3) { animation-delay: 0.4s; }

	@keyframes pulse {
		0%, 80%, 100% { opacity: 0.3; }
		40% { opacity: 1; }
	}

	.answer-actions {
		margin-top: var(--space-4);
		padding-top: var(--space-4);
		border-top: 1px solid var(--color-border);
	}

	.proof-btn {
		display: inline-flex;
		align-items: center;
		padding: var(--space-2) var(--space-4);
		border-radius: var(--radius-md);
		background: var(--color-bg-muted);
		color: var(--color-text-secondary);
		font-size: var(--text-sm);
		font-weight: var(--weight-medium);
		transition: all var(--transition-fast);
	}

	.proof-btn:hover {
		background: var(--color-border);
		color: var(--color-text);
	}
</style>
