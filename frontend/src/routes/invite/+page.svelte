<script lang="ts">
	import { authStore } from '$lib/auth.store.svelte';
	import {
		consumeGoogleRedirect,
		establishBackendSession,
		resendVerificationEmail,
		signInEmail,
		signUpEmail,
		startGoogleSignIn
	} from '$lib/auth';
	import { firebaseAuth } from '$lib/firebase';
	import { goto } from '$app/navigation';

	let email = $state('');
	let password = $state('');
	let busy = $state(false);
	let message = $state<string | null>(null);
	let error = $state<string | null>(null);
	let needsEmailVerification = $state(false);
	let redirectHandled = $state(false);

	async function finishSession() {
		const user = firebaseAuth.currentUser;
		if (!user) return;
		const sessionUser = await establishBackendSession(user);
		authStore.setSignedIn(sessionUser);
		await goto('/');
	}

	async function handleGoogle() {
		error = null;
		message = null;
		needsEmailVerification = false;
		await startGoogleSignIn();
	}

	async function handleEmailSignIn() {
		busy = true;
		error = null;
		message = null;
		needsEmailVerification = false;
		try {
			const user = await signInEmail(email, password);
			await user.reload();
			if (!user.emailVerified) {
				needsEmailVerification = true;
				throw new Error('Email not verified');
			}
			await finishSession();
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			busy = false;
		}
	}

	async function handleEmailSignUp() {
		busy = true;
		error = null;
		message = null;
		needsEmailVerification = false;
		try {
			await signUpEmail(email, password);
			needsEmailVerification = true;
			message = 'Verification email sent. Verify your email, then sign in.';
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			busy = false;
		}
	}

	async function handleResendVerification() {
		busy = true;
		error = null;
		message = null;
		try {
			const user = firebaseAuth.currentUser;
			if (!user) throw new Error('Not signed in');
			await resendVerificationEmail(user);
			message = 'Verification email re-sent.';
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			busy = false;
		}
	}

	$effect(() => {
		if (redirectHandled) return;
		redirectHandled = true;
		// If we just returned from Google sign-in redirect, consume it and
		// establish the backend session.
		(async () => {
			try {
				busy = true;
				const u = await consumeGoogleRedirect();
				if (u) {
					await finishSession();
				}
			} catch (e) {
				error = e instanceof Error ? e.message : String(e);
			} finally {
				busy = false;
			}
		})();
	});
</script>

<svelte:head>
	<title>Invite — PokéProf Notebook</title>
</svelte:head>

<div class="invite">
	<div class="card">
		<h1>Invite-only access</h1>
		<p class="subtext">
			This app is currently invite-only. Sign in, and we will check whether your email is on the allow list.
		</p>

		<div class="section">
			<button class="google" onclick={handleGoogle} disabled={busy}>
				Continue with Google
			</button>
			<p class="hint">Google sign-in works best on mobile.</p>
		</div>

		<div class="divider">
			<span>or</span>
		</div>

		<div class="section">
			<label>
				<span>Email</span>
				<input type="email" bind:value={email} autocomplete="email" placeholder="you@example.com" />
			</label>
			<label>
				<span>Password</span>
				<input type="password" bind:value={password} autocomplete="current-password" />
			</label>
			<div class="actions">
				<button class="primary" onclick={handleEmailSignIn} disabled={busy || !email || !password}>
					Sign in
				</button>
				<button class="secondary" onclick={handleEmailSignUp} disabled={busy || !email || !password}>
					Create account
				</button>
			</div>
			{#if needsEmailVerification}
				<div class="notice notice--warning">
					<strong>Email verification required.</strong>
					<p>
						Check your inbox for a verification email, then sign in again.
					</p>
					<button class="link" onclick={handleResendVerification} disabled={busy}>
						Resend verification email
					</button>
				</div>
			{/if}
		</div>

		{#if message}
			<div class="notice notice--success">{message}</div>
		{/if}
		{#if error}
			<div class="notice notice--error">{error}</div>
		{/if}

		<p class="footer">
			If you believe you should have access, ask an admin to add your email to the allow list.
		</p>
	</div>
</div>

<style>
	.invite {
		padding: var(--space-6) var(--space-4);
		max-width: 520px;
		margin: 0 auto;
	}

	.card {
		background: var(--card-bg);
		border: 1px solid var(--card-border);
		border-radius: var(--radius-lg);
		box-shadow: var(--card-shadow);
		padding: var(--space-6);
	}

	h1 {
		font-size: var(--text-2xl);
		margin-bottom: var(--space-2);
	}

	.subtext {
		color: var(--color-text-secondary);
		margin-bottom: var(--space-5);
	}

	.section {
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
	}

	label span {
		display: block;
		font-size: var(--text-sm);
		color: var(--color-text-secondary);
		margin-bottom: var(--space-1);
	}

	.actions {
		display: flex;
		gap: var(--space-3);
		flex-wrap: wrap;
	}

	button.primary {
		background: var(--color-primary);
		color: var(--color-primary-text);
		border-radius: var(--radius-md);
		padding: var(--space-2) var(--space-4);
	}

	button.primary:hover {
		background: var(--color-primary-hover);
	}

	button.secondary {
		background: var(--color-bg-muted);
		color: var(--color-text);
		border-radius: var(--radius-md);
		padding: var(--space-2) var(--space-4);
	}

	button.secondary:hover {
		background: var(--color-border);
	}

	button.google {
		background: var(--color-bg);
		color: var(--color-text);
		border: 1px solid var(--color-border-strong);
		border-radius: var(--radius-md);
		padding: var(--space-2) var(--space-4);
	}

	button.google:hover {
		background: var(--color-bg-muted);
	}

	button:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.hint {
		color: var(--color-text-muted);
		font-size: var(--text-sm);
	}

	.divider {
		display: flex;
		align-items: center;
		gap: var(--space-3);
		margin: var(--space-5) 0;
		color: var(--color-text-muted);
		font-size: var(--text-sm);
	}

	.divider::before,
	.divider::after {
		content: '';
		flex: 1;
		height: 1px;
		background: var(--color-border);
	}

	.notice {
		margin-top: var(--space-4);
		border-radius: var(--radius-md);
		padding: var(--space-3) var(--space-4);
		font-size: var(--text-sm);
	}

	.notice p {
		margin-top: var(--space-2);
	}

	.notice--success {
		background: var(--color-success-subtle);
		color: var(--color-text);
	}

	.notice--warning {
		background: var(--color-warning-subtle);
		color: var(--color-text);
	}

	.notice--error {
		background: var(--color-error-subtle);
		color: var(--color-text);
	}

	button.link {
		min-height: auto;
		min-width: auto;
		padding: 0;
		text-decoration: underline;
		color: var(--color-link);
		margin-top: var(--space-2);
	}

	.footer {
		margin-top: var(--space-5);
		color: var(--color-text-muted);
		font-size: var(--text-sm);
	}
</style>
