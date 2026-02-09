/** TypeScript interfaces mirroring Python types.py */

export type DocumentType =
	| 'rulebook'
	| 'penalty_guidelines'
	| 'legal_card_list'
	| 'rulings_compendium'
	| 'card_database';

export type Persona = 'judge' | 'professor' | 'player';

export interface NodeMetadata {
	document_type: DocumentType;
	section_number: string;
	title: string;
}

export interface TreeNode {
	id: string;
	content: string;
	metadata: NodeMetadata;
	children: TreeNode[];
	token_count: number;
}

export interface DocumentIndex {
	document_name: string;
	document_type: DocumentType;
	root: TreeNode;
	total_tokens: number;
	source_hash: string;
}

export interface RetrievedSection {
	section_number: string;
	title: string;
	score: number;
	document_name: string;
}

export interface RouteDecision {
	documents: string[];
	confidence: number;
	reasoning: string;
}

export interface IndexSummary {
	name: string;
	document_type: DocumentType;
	node_count: number;
	total_tokens: number;
}

export type QueryStage = 'idle' | 'routing' | 'retrieving' | 'streaming' | 'done' | 'error';

export interface RecentQuery {
	query: string;
	persona: Persona;
	timestamp: number;
}
