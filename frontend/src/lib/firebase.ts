import { initializeApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';

function requiredEnv(name: string): string {
	const v = (import.meta as any).env?.[name] as string | undefined;
	if (!v) throw new Error(`Missing required env var: ${name}`);
	return v;
}

export const firebaseApp = initializeApp({
	apiKey: requiredEnv('VITE_FIREBASE_API_KEY'),
	authDomain: requiredEnv('VITE_FIREBASE_AUTH_DOMAIN'),
	projectId: requiredEnv('VITE_FIREBASE_PROJECT_ID'),
	appId: requiredEnv('VITE_FIREBASE_APP_ID')
});

export const firebaseAuth = getAuth(firebaseApp);
export const googleProvider = new GoogleAuthProvider();
