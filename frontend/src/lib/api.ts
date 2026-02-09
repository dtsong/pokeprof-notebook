/** API client for PokéProf Notebook backend */

import type { Persona, IndexSummary, TreeNode } from './types';
import { queryStore, recentStore } from './stores.svelte';

let activeSource: EventSource | null = null;

export function submitQuery(query: string, persona: Persona) {
	cancelQuery();
	queryStore.startQuery(query);

	const params = new URLSearchParams({ q: query, persona });
	const source = new EventSource(`/api/query?${params}`);
	activeSource = source;

	source.addEventListener('route', (e) => {
		const data = JSON.parse(e.data);
		queryStore.setRoute(data);
	});

	source.addEventListener('sections', (e) => {
		const data = JSON.parse(e.data);
		queryStore.setSections(data);
	});

	source.addEventListener('token', (e) => {
		queryStore.appendToken(e.data);
	});

	source.addEventListener('error', (e) => {
		if (e instanceof MessageEvent && e.data) {
			queryStore.setError(e.data);
		} else if (queryStore.stage !== 'done') {
			queryStore.setError('Connection lost. Please try again.');
		}
		source.close();
		activeSource = null;
	});

	source.addEventListener('done', () => {
		queryStore.setDone();
		recentStore.add(query, persona);
		source.close();
		activeSource = null;
	});
}

export function cancelQuery() {
	if (activeSource) {
		activeSource.close();
		activeSource = null;
	}
	queryStore.reset();
}

export async function fetchIndexes(): Promise<IndexSummary[]> {
	const res = await fetch('/api/indexes');
	if (!res.ok) throw new Error(`Failed to fetch indexes: ${res.status}`);
	return res.json();
}

export async function fetchTree(name: string): Promise<TreeNode> {
	const res = await fetch(`/api/indexes/${encodeURIComponent(name)}/tree`);
	if (!res.ok) throw new Error(`Failed to fetch tree: ${res.status}`);
	return res.json();
}

export async function fetchNode(indexName: string, nodeId: string): Promise<TreeNode> {
	const res = await fetch(
		`/api/indexes/${encodeURIComponent(indexName)}/node/${encodeURIComponent(nodeId)}`
	);
	if (!res.ok) throw new Error(`Failed to fetch node: ${res.status}`);
	return res.json();
}
