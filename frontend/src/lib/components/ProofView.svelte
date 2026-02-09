<script lang="ts">
	import { marked } from 'marked';

	let { content, onClose }: { content: string; onClose: () => void } = $props();

	let wakeLock: WakeLockSentinel | null = $state(null);

	const renderedHtml = $derived(content ? marked.parse(content) as string : '');

	async function acquireWakeLock() {
		try {
			if ('wakeLock' in navigator) {
				wakeLock = await navigator.wakeLock.request('screen');
			}
		} catch {
			// Graceful no-op on unsupported browsers or if denied
		}
	}

	async function releaseWakeLock() {
		if (wakeLock) {
			await wakeLock.release();
			wakeLock = null;
		}
	}

	function handleClose() {
		releaseWakeLock();
		onClose();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			handleClose();
		}
	}

	$effect(() => {
		acquireWakeLock();
		return () => { releaseWakeLock(); };
	});
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div class="proof-overlay" onclick={handleClose}>
	<div class="proof-content prose">
		{@html renderedHtml}
	</div>
	<div class="proof-hint">Tap anywhere or press Escape to close</div>
</div>

<style>
	.proof-overlay {
		position: fixed;
		inset: 0;
		z-index: 1000;
		background: var(--proof-bg);
		color: var(--proof-text);
		overflow-y: auto;
		-webkit-overflow-scrolling: touch;
		padding: var(--space-8);
		padding-top: calc(env(safe-area-inset-top, 0px) + var(--space-8));
		padding-bottom: calc(env(safe-area-inset-bottom, 0px) + var(--space-16));
		cursor: pointer;
	}

	.proof-content {
		max-width: 720px;
		margin: 0 auto;
		font-size: 1.5rem;
		line-height: 1.6;
	}

	.proof-content :global(h1),
	.proof-content :global(h2),
	.proof-content :global(h3) {
		color: var(--proof-text);
	}

	.proof-content :global(code) {
		background: rgba(255, 255, 255, 0.1);
		color: var(--proof-text);
	}

	.proof-content :global(pre) {
		background: rgba(255, 255, 255, 0.06);
	}

	.proof-content :global(a) {
		color: var(--navy-300);
	}

	.proof-content :global(strong) {
		color: var(--proof-text);
		font-weight: var(--weight-bold);
	}

	.proof-content :global(blockquote) {
		border-left-color: rgba(255, 255, 255, 0.3);
		color: rgba(255, 255, 255, 0.8);
	}

	.proof-content :global(table) {
		color: var(--proof-text);
	}

	.proof-content :global(th),
	.proof-content :global(td) {
		border-bottom-color: rgba(255, 255, 255, 0.15);
	}

	.proof-hint {
		position: fixed;
		bottom: calc(env(safe-area-inset-bottom, 0px) + var(--space-4));
		left: 50%;
		transform: translateX(-50%);
		font-size: var(--text-xs);
		color: rgba(255, 255, 255, 0.35);
		pointer-events: none;
	}

	@media (min-width: 768px) {
		.proof-content {
			font-size: 1.75rem;
			line-height: 1.7;
		}
	}
</style>
