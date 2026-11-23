import type { components } from '@/generated/api/agent-api';

type Schemas = components['schemas'];

export type AgentConfig = Record<string, unknown>;
export interface AgentDraft { content: AgentConfig; revision: number; content_hash: string; updated_at: string; updated_by: string }
export interface AgentIssue { path: string; code: string; message: string }
export interface AgentValidation { valid: boolean; content_hash: string; issues: AgentIssue[]; draft_revision: number }
export interface AgentReleaseSummary {
  id: string; version: number; content_hash: string; draft_revision: number; note: string | null;
  created_at: string; created_by: string; is_active: boolean;
}
export interface AgentRelease extends AgentReleaseSummary { content: AgentConfig }
export interface AgentActive { release_id: string; version: number; content_hash: string; revision: number; updated_at: string; updated_by: string }
export interface AuditEvent {
  id: string; at: string; actor: string; action: string; before_ref: string | null; after_ref: string | null;
  outcome: 'success' | 'rejected'; details: Record<string, unknown>;
}
export interface Page<T> { items: T[]; next_cursor: string | null }

export interface ChatflowNode {
  id: string;
  type: Schemas['ChatflowNodeType'];
  title?: string;
  /** Authoring note; the runtime never reads it. */
  description?: string;
  config?: Record<string, unknown>;
  ui?: { position?: { x: number; y: number } };
}
export interface ChatflowEdge {
  id: string;
  source: string;
  source_handle: string;
  target: string;
}
export type VariableType = 'string' | 'number' | 'boolean' | 'enum' | 'string_list';
/** Per-type limits; mirror of agent_runtime VariableConstraints. */
export interface VariableConstraints {
  min_length?: number;
  max_length?: number;
  minimum?: number;
  maximum?: number;
  integer?: boolean;
  max_items?: number;
  item_max_length?: number;
}
export interface ChatflowVariable {
  name: string;
  description?: string;
  type: VariableType;
  values?: string[];
  default: unknown;
  constraints?: VariableConstraints;
}
export type ChatflowBudget = { max_nodes?: number; max_llm_calls?: number; turn_timeout_ms?: number };
/**
 * One graph as the canvas, node form and variables panel edit it: a flow's entry, nodes and edges plus the
 * chatflow's shared variables and budget (see model/workflow/flows.ts `flowView`).
 */
export interface ChatflowWorkflow {
  entry: string;
  variables?: ChatflowVariable[];
  nodes: ChatflowNode[];
  edges?: ChatflowEdge[];
  budget?: ChatflowBudget;
  /** Node ids of the other flows: new ids must avoid them too. View-only; never written to the draft. */
  takenNodeIds?: string[];
}
/** One business flow (nghiệp vụ); mirror of agent_runtime `Flow`. */
export interface ChatflowFlow {
  id: string;
  title: string;
  /** Read by the router to pick this flow; required while the flow is routable. */
  description?: string;
  examples?: string[];
  /** DEC-23 condition; a match routes the turn here before anything else. */
  trigger?: Record<string, unknown> | null;
  routable?: boolean;
  entry: string;
  nodes: ChatflowNode[];
  edges?: ChatflowEdge[];
}
export interface ChatflowRouter {
  default_flow: string;
  model?: string | null;
  instructions?: string;
  history_messages?: number;
}
/** The draft's `workflow`: shared variables and budget, the router and one to ten flows. */
export interface Chatflow {
  variables?: ChatflowVariable[];
  budget?: ChatflowBudget;
  router: ChatflowRouter;
  flows: ChatflowFlow[];
}
export type ChatflowNodeType = Schemas['ChatflowNodeType'];
export type WorkflowNodeType = Schemas['WorkflowNodeType'];
export type WorkflowNodeTypeCatalog = Schemas['WorkflowNodeTypeCatalog'];
export type WorkflowNamespace = Schemas['WorkflowNamespace'];
export type WorkflowHandleSpec = Schemas['WorkflowHandleSpec'];
export type NodeTypeCatalog = WorkflowNodeTypeCatalog;

export type WorkflowDebugRunRequest = Schemas['WorkflowDebugRunRequest'];
export type WorkflowDebugRunResult = Schemas['WorkflowDebugRunResult'];
export type WorkflowDebugNodeRun = Schemas['WorkflowDebugNodeRun'];
export type WorkflowDebugStreamEvent = Schemas['WorkflowDebugStreamEvent'];
