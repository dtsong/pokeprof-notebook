<script lang="ts">
	import { marked } from 'marked';

	let { content }: { content: string } = $props();

	let html = $derived(marked.parse(content) as string);
</script>

<article class="content-viewer">
	<div class="prose">
		{@html html}
	</div>
</article>

<style>
	.content-viewer {
		padding: var(--space-4) 0;
	}
</style>
