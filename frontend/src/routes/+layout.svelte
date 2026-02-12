<script>
	import '../app.css';
	import AppShell from '$lib/components/AppShell.svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { authStore } from '$lib/auth.store.svelte';
	let { children } = $props();

	$effect(() => {
		authStore.bootstrap();
	});

	$effect(() => {
		if (!authStore.bootstrapped) return;
		// Cast to string to avoid typed-route narrowing in some editor setups.
		const pathname = String(page.url.pathname);
		if (authStore.status === 'signed_out' && pathname !== '/invite') {
			goto('/invite');
		}
		if (authStore.status === 'signed_in' && pathname === '/invite') {
			goto('/');
		}
	});
</script>

<AppShell>
	{@render children()}
</AppShell>
