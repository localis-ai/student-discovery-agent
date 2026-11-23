import { parsePath, type Path } from '../config';
import type { AgentIssue, Chatflow, ChatflowWorkflow } from '../../types';
import { flowView } from './flows';

/** `flowId`: the flow (nghiệp vụ) a node or edge lives in, when the path came from a whole chatflow. */
export type WorkflowIssueTarget =
  | { kind: 'workflow'; configPath?: Path }
  | { kind: 'flow'; flowId: string; flowIndex: number; flowTitle?: string; configPath: Path }
  | { kind: 'node'; nodeId: string; nodeIndex: number; configPath: Path; flowId?: string }
  | { kind: 'edge'; edgeId: string; edgeIndex: number; configPath: Path; flowId?: string }
  | { kind: 'variable'; variableIndex: number; variableName?: string; configPath: Path };

export function workflowIssueLabel(target: WorkflowIssueTarget): string {
  if (target.kind === 'node') return `node ${target.nodeId}`;
  if (target.kind === 'edge') return `edge ${target.edgeId}`;
  if (target.kind === 'variable') return target.variableName ? `biến ${target.variableName}` : `biến #${target.variableIndex + 1}`;
  if (target.kind === 'flow') return `nghiệp vụ ${target.flowTitle ?? target.flowId}`;
  return 'toàn bộ workflow';
}

export function workflowIssueKey(target: WorkflowIssueTarget): string {
  if (target.kind === 'node') return `node:${target.nodeId}`;
  if (target.kind === 'edge') return `edge:${target.flowId ?? ''}:${target.edgeId}`;
  if (target.kind === 'variable') return `variable:${target.variableIndex}`;
  if (target.kind === 'flow') return `flow:${target.flowId}`;
  return 'workflow';
}

const FLOW_PATH = /^workflow\.flows\[(\d+)\](.*)$/;

/**
 * Maps a validator path of a whole chatflow (`workflow.flows[k].nodes[i]…`, `workflow.variables[i]`,
 * `workflow.router…`) to what it points at; nodes and edges carry the id of their flow.
 */
export function parseChatflowIssuePath(path: string, chat: Chatflow): WorkflowIssueTarget {
  const match = FLOW_PATH.exec(path);
  if (!match) {
    if (path.startsWith('workflow.router')) return { kind: 'workflow', configPath: parsePath(path).slice(1) };
    return chat.flows.length ? parseWorkflowIssuePath(path, flowView(chat, chat.flows[0]!.id)) : { kind: 'workflow' };
  }
  const index = Number(match[1]);
  const rest = match[2] ?? '';
  const flow = chat.flows[index];
  if (!flow) return { kind: 'workflow' };
  if (rest.startsWith('.nodes') || rest.startsWith('.edges') || rest === '.entry') {
    const target = parseWorkflowIssuePath(`workflow${rest}`, flowView(chat, flow.id));
    // An index past the flow's nodes (a report on an older draft) points at nothing in particular.
    return target.kind === 'node' || target.kind === 'edge' ? { ...target, flowId: flow.id } : target;
  }
  return { kind: 'flow', flowId: flow.id, flowIndex: index, flowTitle: flow.title, configPath: parsePath(`x${rest}`).slice(1) };
}

/** The issues of one flow, with paths rewritten to that flow's view (`workflow.nodes[i]…`) for the canvas. */
export function issuesForFlow(issues: AgentIssue[], chat: Chatflow, flowId: string): AgentIssue[] {
  const index = chat.flows.findIndex(flow => flow.id === flowId);
  const prefix = `workflow.flows[${index}]`;
  return issues.flatMap(issue => (issue.path.startsWith(`${prefix}.`)
    ? [{ ...issue, path: `workflow${issue.path.slice(prefix.length)}` }] : []));
}

const escapeRegex = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

function lineRangeAt(text: string, start: number): { start: number; end: number } {
  const lineEnd = text.indexOf('\n', start);
  return { start, end: lineEnd >= 0 ? lineEnd : text.length };
}

function findEnclosingObjectSpan(text: string, anchor: number): { start: number; end: number } | null {
  const stack: number[] = [];
  let inString = false;
  let escaped = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (inString) {
      if (escaped) escaped = false;
      else if (ch === '\\') escaped = true;
      else if (ch === '"') inString = false;
      continue;
    }
    if (ch === '"') { inString = true; continue; }
    if (ch === '{') { stack.push(i); continue; }
    if (ch === '}') {
      const start = stack.pop();
      if (start !== undefined && start <= anchor && anchor <= i) return { start, end: i + 1 };
    }
  }
  return null;
}

function findPropertyInSpan(text: string, key: string, span: { start: number; end: number }): number {
  const slice = text.slice(span.start, span.end);
  const match = new RegExp(`"${escapeRegex(key)}"\\s*:`).exec(slice);
  return match ? span.start + match.index : -1;
}

function findConfigPathStart(text: string, configPath: Path, span: { start: number; end: number }): number {
  let cursor = span.start;
  let lastFound = -1;
  for (const part of configPath) {
    if (typeof part !== 'string') continue;
    const found = findPropertyInSpan(text, part, { start: cursor, end: span.end });
    if (found < 0) break;
    lastFound = found;
    cursor = found + part.length + 2;
  }
  return lastFound;
}

/** Finds a character range inside formatted workflow JSON to highlight for a validator issue target. */
export function findWorkflowIssueRange(
  jsonText: string,
  target: WorkflowIssueTarget,
): { start: number; end: number } | null {
  if (!jsonText) return null;

  if (target.kind === 'node' || target.kind === 'edge') {
    const id = target.kind === 'node' ? target.nodeId : target.edgeId;
    const idMatch = new RegExp(`"id"\\s*:\\s*"${escapeRegex(id)}"`).exec(jsonText);
    if (!idMatch) return null;
    const span = findEnclosingObjectSpan(jsonText, idMatch.index);
    const fieldStart = span ? findConfigPathStart(jsonText, target.configPath, span) : -1;
    return lineRangeAt(jsonText, fieldStart >= 0 ? fieldStart : idMatch.index);
  }

  if (target.kind === 'variable') {
    if (target.variableName) {
      const varMatch = new RegExp(`"name"\\s*:\\s*"${escapeRegex(target.variableName)}"`).exec(jsonText);
      if (varMatch) {
        const span = findEnclosingObjectSpan(jsonText, varMatch.index);
        const fieldStart = span ? findConfigPathStart(jsonText, target.configPath, span) : -1;
        return lineRangeAt(jsonText, fieldStart >= 0 ? fieldStart : varMatch.index);
      }
    }
    const varsStart = findPropertyInSpan(jsonText, 'variables', { start: 0, end: jsonText.length });
    return varsStart >= 0 ? lineRangeAt(jsonText, varsStart) : null;
  }

  if (target.configPath && target.configPath.length > 0) {
    const start = findConfigPathStart(jsonText, target.configPath, { start: 0, end: jsonText.length });
    if (start >= 0) return lineRangeAt(jsonText, start);
  }

  return null;
}

const workflowTarget = (): WorkflowIssueTarget => ({ kind: 'workflow' });

/** Maps a validator path to the workflow object it should highlight or focus. */
export function parseWorkflowIssuePath(
  path: string,
  workflow: ChatflowWorkflow,
): WorkflowIssueTarget {
  const parts = parsePath(path);
  if (parts[0] !== 'workflow' || typeof parts[1] !== 'string') return workflowTarget();

  const collection = parts[1];
  if (collection === 'entry' && parts.length === 2)
    return { kind: 'workflow', configPath: ['entry'] };
  if (collection === 'budget') return { kind: 'workflow', configPath: parts.slice(1) };

  const index = parts[2];
  if (typeof index !== 'number' || !Number.isInteger(index) || index < 0) return workflowTarget();

  if (collection === 'nodes') {
    const node = Array.isArray(workflow?.nodes) ? workflow.nodes[index] : undefined;
    if (!node || typeof node.id !== 'string' || !node.id) return workflowTarget();
    const remainder = parts.slice(3);
    return {
      kind: 'node',
      nodeId: node.id,
      nodeIndex: index,
      configPath: remainder[0] === 'config' ? remainder.slice(1) : remainder,
    };
  }

  if (collection === 'edges') {
    const edge = Array.isArray(workflow?.edges) ? workflow.edges[index] : undefined;
    if (!edge || typeof edge.id !== 'string' || !edge.id) return workflowTarget();
    return { kind: 'edge', edgeId: edge.id, edgeIndex: index, configPath: parts.slice(3) };
  }

  if (collection === 'variables') {
    const variable = Array.isArray(workflow?.variables) ? workflow.variables[index] : undefined;
    if (!variable) return workflowTarget();
    return {
      kind: 'variable',
      variableIndex: index,
      variableName: typeof variable.name === 'string' ? variable.name : undefined,
      configPath: parts.slice(3),
    };
  }

  return workflowTarget();
}
