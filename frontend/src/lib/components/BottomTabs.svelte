<script lang="ts">
	import { page } from '$app/state';

	const tabs = [
		{ href: '/', label: 'Search', icon: 'search' },
		{ href: '/browse', label: 'Browse', icon: 'browse' }
	] as const;

	const isActive = (href: string) => {
		if (href === '/') return page.url.pathname === '/';
		return page.url.pathname.startsWith(href);
	};
</script>

<nav class="bottom-tabs" aria-label="Main navigation">
	{#each tabs as tab}
		<a
			href={tab.href}
			class="tab"
			class:active={isActive(tab.href)}
			aria-current={isActive(tab.href) ? 'page' : undefined}
		>
			<svg class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				{#if tab.icon === 'search'}
					<circle cx="11" cy="11" r="8" />
					<line x1="21" y1="21" x2="16.65" y2="16.65" />
				{:else}
					<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
					<path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
				{/if}
			</svg>
			<span class="tab-label">{tab.label}</span>
		</a>
	{/each}
</nav>

<style>
	.bottom-tabs {
		display: flex;
		border-top: 1px solid var(--nav-border);
		background: var(--nav-bg);
		padding-bottom: env(safe-area-inset-bottom, 0);
	}

	.tab {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: var(--space-1);
		padding: var(--space-2) var(--space-2);
		min-height: var(--touch-min);
		color: var(--nav-inactive);
		text-decoration: none;
		transition: color var(--transition-fast);
		-webkit-tap-highlight-color: transparent;
	}

	.tab:hover {
		color: var(--color-text-secondary);
	}

	.tab.active {
		color: var(--nav-active);
	}

	.tab-icon {
		width: 22px;
		height: 22px;
	}

	.tab-label {
		font-size: var(--text-xs);
		font-weight: var(--weight-medium);
	}

	@media (display-mode: standalone) {
		.bottom-tabs {
			padding-bottom: env(safe-area-inset-bottom, 8px);
		}
	}
</style>
