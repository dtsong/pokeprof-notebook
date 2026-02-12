import {
	createUserWithEmailAndPassword,
	getRedirectResult,
	sendEmailVerification,
	signInWithEmailAndPassword,
	signInWithRedirect,
	signOut,
	type User
} from 'firebase/auth';

import { firebaseAuth, googleProvider } from './firebase';

export interface SessionUser {
	uid: string;
	email: string;
	role: string;
	name?: string;
}

export interface MeResponse {
	authenticated: boolean;
	user: SessionUser | null;
}

export async function fetchMe(): Promise<MeResponse> {
	const res = await fetch('/api/me');
	if (!res.ok) throw new Error(`Failed to fetch /api/me: ${res.status}`);
	return res.json();
}

export async function establishBackendSession(user: User): Promise<SessionUser> {
	const token = await user.getIdToken();
	const res = await fetch('/api/session', {
		method: 'POST',
		headers: {
			Authorization: `Bearer ${token}`
		}
	});

	if (res.status === 403) {
		// Not invited or email not verified.
		const data = await res.json().catch(() => null);
		const detail = data?.detail || 'Access forbidden';
		throw new Error(detail);
	}

	if (!res.ok) {
		const data = await res.json().catch(() => null);
		const detail = data?.detail || `Failed to create session (${res.status})`;
		throw new Error(detail);
	}

	const data = (await res.json()) as { ok: boolean; user: SessionUser };
	return data.user;
}

export async function signInEmail(email: string, password: string): Promise<User> {
	const cred = await signInWithEmailAndPassword(firebaseAuth, email, password);
	return cred.user;
}

export async function signUpEmail(email: string, password: string): Promise<User> {
	const cred = await createUserWithEmailAndPassword(firebaseAuth, email, password);
	// Send verification email immediately.
	await sendEmailVerification(cred.user);
	return cred.user;
}

export async function resendVerificationEmail(user: User): Promise<void> {
	await sendEmailVerification(user);
}

export async function startGoogleSignIn(): Promise<void> {
	await signInWithRedirect(firebaseAuth, googleProvider);
}

export async function consumeGoogleRedirect(): Promise<User | null> {
	const result = await getRedirectResult(firebaseAuth);
	return result?.user || null;
}

export async function logoutEverywhere(): Promise<void> {
	await fetch('/api/logout', { method: 'POST' }).catch(() => null);
	await signOut(firebaseAuth);
}
