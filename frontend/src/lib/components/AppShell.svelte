<script lang="ts">
	import BottomTabs from './BottomTabs.svelte';
	import { page } from '$app/state';

	let { children } = $props();

	const tabs = [
		{ href: '/', label: 'Search', icon: 'search' },
		{ href: '/browse', label: 'Browse', icon: 'browse' }
	] as const;

	const isActive = (href: string) => {
		if (href === '/') return page.url.pathname === '/';
		return page.url.pathname.startsWith(href);
	};
</script>

<div class="shell">
	<!-- Desktop sidebar -->
	<nav class="sidebar" aria-label="Main navigation">
		<div class="sidebar-brand">
			<span class="brand-accent">Poké</span>Prof
		</div>
		{#each tabs as tab}
			<a
				href={tab.href}
				class="sidebar-link"
				class:active={isActive(tab.href)}
				aria-current={isActive(tab.href) ? 'page' : undefined}
			>
				<svg class="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					{#if tab.icon === 'search'}
						<circle cx="11" cy="11" r="8" />
						<line x1="21" y1="21" x2="16.65" y2="16.65" />
					{:else}
						<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
						<path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
					{/if}
				</svg>
				{tab.label}
			</a>
		{/each}
	</nav>

	<!-- Mobile header -->
	<header class="mobile-header">
		<span class="brand-accent">Poké</span>Prof
	</header>

	<main class="content">
		{@render children()}
	</main>

	<!-- Mobile bottom tabs -->
	<div class="mobile-nav">
		<BottomTabs />
	</div>
</div>

<style>
	.shell {
		display: flex;
		flex-direction: column;
		min-height: 100dvh;
	}

	.content {
		flex: 1;
		overflow-y: auto;
		-webkit-overflow-scrolling: touch;
	}

	/* ── Mobile ── */
	.sidebar {
		display: none;
	}

	.mobile-header {
		display: flex;
		align-items: center;
		padding: var(--space-3) var(--space-4);
		padding-top: calc(env(safe-area-inset-top, 0px) + var(--space-3));
		border-bottom: 1px solid var(--nav-border);
		background: var(--nav-bg);
		font-size: var(--text-lg);
		font-weight: var(--weight-bold);
	}

	.mobile-nav {
		display: block;
	}

	.brand-accent {
		color: var(--color-accent);
	}

	/* ── Desktop ── */
	@media (min-width: 768px) {
		.shell {
			flex-direction: row;
		}

		.sidebar {
			display: flex;
			flex-direction: column;
			width: 220px;
			min-width: 220px;
			border-right: 1px solid var(--nav-border);
			background: var(--color-bg-subtle);
			padding: var(--space-4);
			gap: var(--space-1);
		}

		.sidebar-brand {
			font-size: var(--text-lg);
			font-weight: var(--weight-bold);
			padding: var(--space-2) var(--space-3);
			margin-bottom: var(--space-4);
		}

		.sidebar-link {
			display: flex;
			align-items: center;
			gap: var(--space-3);
			padding: var(--space-3);
			border-radius: var(--radius-md);
			color: var(--color-text-secondary);
			text-decoration: none;
			font-weight: var(--weight-medium);
			transition: all var(--transition-fast);
		}

		.sidebar-link:hover {
			background: var(--color-bg-muted);
			color: var(--color-text);
		}

		.sidebar-link.active {
			background: var(--color-primary);
			color: var(--color-primary-text);
		}

		.sidebar-icon {
			width: 20px;
			height: 20px;
			flex-shrink: 0;
		}

		.mobile-header {
			display: none;
		}

		.mobile-nav {
			display: none;
		}

		.content {
			flex: 1;
			min-width: 0;
		}
	}

	/* ── PWA standalone mode ── */
	@media (display-mode: standalone) {
		.mobile-header {
			padding-top: calc(env(safe-area-inset-top, 20px) + var(--space-3));
		}
	}
</style>
