/** Svelte 5 rune stores for PokéProf Notebook */

import type {
	Persona,
	QueryStage,
	RecentQuery,
	RetrievedSection,
	RouteDecision,
	IndexSummary,
	TreeNode
} from './types';

// ── Query Store ──

const RECENT_KEY = 'pokeprof-recent-queries';
const MAX_RECENT = 20;

function createQueryStore() {
	let stage = $state<QueryStage>('idle');
	let query = $state('');
	let persona = $state<Persona>('judge');
	let answer = $state('');
	let route = $state<RouteDecision | null>(null);
	let sections = $state<RetrievedSection[]>([]);
	let error = $state<string | null>(null);

	return {
		get stage() { return stage; },
		get query() { return query; },
		get persona() { return persona; },
		get answer() { return answer; },
		get route() { return route; },
		get sections() { return sections; },
		get error() { return error; },

		setPersona(p: Persona) { persona = p; },

		startQuery(q: string) {
			stage = 'routing';
			query = q;
			answer = '';
			route = null;
			sections = [];
			error = null;
		},

		setRoute(r: RouteDecision) {
			route = r;
			stage = 'retrieving';
		},

		setSections(s: RetrievedSection[]) {
			sections = s;
			stage = 'streaming';
		},

		appendToken(token: string) {
			answer += token;
		},

		setDone() {
			stage = 'done';
		},

		setError(msg: string) {
			error = msg;
			stage = 'error';
		},

		reset() {
			stage = 'idle';
			query = '';
			answer = '';
			route = null;
			sections = [];
			error = null;
		}
	};
}

export const queryStore = createQueryStore();

// ── Recent Queries Store ──

function loadRecent(): RecentQuery[] {
	if (typeof localStorage === 'undefined') return [];
	try {
		return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]');
	} catch {
		return [];
	}
}

function saveRecent(items: RecentQuery[]) {
	if (typeof localStorage === 'undefined') return;
	localStorage.setItem(RECENT_KEY, JSON.stringify(items));
}

function createRecentStore() {
	let items = $state<RecentQuery[]>(loadRecent());

	return {
		get items() { return items; },

		add(query: string, persona: Persona) {
			items = [
				{ query, persona, timestamp: Date.now() },
				...items.filter((r) => r.query !== query)
			].slice(0, MAX_RECENT);
			saveRecent(items);
		},

		clear() {
			items = [];
			saveRecent(items);
		}
	};
}

export const recentStore = createRecentStore();

// ── Browse Store ──

function createBrowseStore() {
	let indexes = $state<IndexSummary[]>([]);
	let selectedDocument = $state<string | null>(null);
	let tree = $state<TreeNode | null>(null);
	let selectedNodeId = $state<string | null>(null);
	let nodeContent = $state<string | null>(null);
	let loading = $state(false);
	let error = $state<string | null>(null);

	return {
		get indexes() { return indexes; },
		get selectedDocument() { return selectedDocument; },
		get tree() { return tree; },
		get selectedNodeId() { return selectedNodeId; },
		get nodeContent() { return nodeContent; },
		get loading() { return loading; },
		get error() { return error; },

		setIndexes(list: IndexSummary[]) { indexes = list; },
		setSelectedDocument(name: string | null) {
			selectedDocument = name;
			tree = null;
			selectedNodeId = null;
			nodeContent = null;
		},
		setTree(t: TreeNode) { tree = t; },
		setSelectedNode(id: string | null) { selectedNodeId = id; },
		setNodeContent(content: string | null) { nodeContent = content; },
		setLoading(v: boolean) { loading = v; },
		setError(msg: string | null) { error = msg; }
	};
}

export const browseStore = createBrowseStore();
