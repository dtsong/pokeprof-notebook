<script lang="ts">
	import { queryStore } from '$lib/stores.svelte';
	import SearchBar from '$lib/components/SearchBar.svelte';
	import PersonaToggle from '$lib/components/PersonaToggle.svelte';
	import AnswerCard from '$lib/components/AnswerCard.svelte';
	import SectionBadges from '$lib/components/SectionBadges.svelte';
	import ErrorBanner from '$lib/components/ErrorBanner.svelte';
	import RecentQueries from '$lib/components/RecentQueries.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';

	let showProof = $state(false);
</script>

<svelte:head>
	<title>Search — PokéProf Notebook</title>
</svelte:head>

<div class="page">
	<div class="search-controls">
		<SearchBar />
		<PersonaToggle />
	</div>

	<ErrorBanner />

	{#if queryStore.stage === 'idle'}
		<EmptyState />
		<RecentQueries />
	{:else}
		<div class="results">
			<SectionBadges />
			<AnswerCard onShowProof={() => { showProof = true; }} />
		</div>
	{/if}
</div>

{#if showProof}
	{#await import('$lib/components/ProofView.svelte') then { default: ProofView }}
		<ProofView content={queryStore.answer} onClose={() => { showProof = false; }} />
	{/await}
{/if}

<style>
	.search-controls {
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
		margin-bottom: var(--space-6);
	}

	.results {
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
	}
</style>
