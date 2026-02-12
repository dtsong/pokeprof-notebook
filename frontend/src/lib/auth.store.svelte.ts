import type { SessionUser } from './auth';
import { fetchMe } from './auth';

export type AuthStatus =
	| 'unknown'
	| 'signed_out'
	| 'signed_in';

function createAuthStore() {
	let status = $state<AuthStatus>('unknown');
	let user = $state<SessionUser | null>(null);
	let error = $state<string | null>(null);
	let bootstrapped = $state(false);

	return {
		get status() { return status; },
		get user() { return user; },
		get error() { return error; },
		get bootstrapped() { return bootstrapped; },

		async bootstrap() {
			if (bootstrapped) return;
			bootstrapped = true;
			try {
				const me = await fetchMe();
				if (me.authenticated && me.user) {
					status = 'signed_in';
					user = me.user;
				} else {
					status = 'signed_out';
					user = null;
				}
			} catch (e) {
				error = e instanceof Error ? e.message : String(e);
				status = 'signed_out';
				user = null;
			}
		},

		setSignedIn(u: SessionUser) {
			status = 'signed_in';
			user = u;
			error = null;
		},

		setSignedOut() {
			status = 'signed_out';
			user = null;
		},

		setError(msg: string) {
			error = msg;
		}
	};
}

export const authStore = createAuthStore();
