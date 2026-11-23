import type { AgentConfig, Chatflow, ChatflowNode, ChatflowVariable, ChatflowWorkflow } from '../../types';
import { isRenderableChatflow } from './flows';

// Same placeholder grammar as agent_runtime/workflow/templates.py PLACEHOLDER (spaces allowed inside the braces).
function placeholder(path: string): RegExp {
  return new RegExp(`\\{\\{\\s*${path.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*\\}\\}`, 'g');
}

/** Deep-maps every string in a JSON value, keeping its shape. */
function mapStrings(value: unknown, fn: (text: string) => string): unknown {
  if (typeof value === 'string') return fn(value);
  if (Array.isArray(value)) return value.map((item) => mapStrings(item, fn));
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, mapStrings(item, fn)]));
  }
  return value;
}

/** Whether a config mentions the path as a whole string (var operand, assign target, missing) or as a placeholder. */
function mentions(value: unknown, path: string): boolean {
  let found = false;
  const template = placeholder(path);
  mapStrings(value, (text) => {
    template.lastIndex = 0;
    if (text === path || template.test(text)) found = true;
    return text;
  });
  return found;
}

/** Ids of the nodes that read or write `conv.<name>`, in workflow order. */
export function variableUsage(workflow: ChatflowWorkflow, name: string): string[] {
  const path = `conv.${name}`;
  return workflow.nodes.filter((node) => mentions(node.config ?? {}, path)).map((node) => node.id);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

/** Ids of the nodes that compare `conv.<name>` with `value` or assign it that value. */
export function enumValueUsage(workflow: ChatflowWorkflow, name: string, value: string): string[] {
  const path = `conv.${name}`;
  const isVar = (operand: unknown) => isRecord(operand) && operand.var === path;
  const matches = (operand: unknown) => operand === value || (Array.isArray(operand) && operand.includes(value));
  const hit = (raw: unknown): boolean => {
    if (Array.isArray(raw)) return raw.some(hit);
    if (!isRecord(raw)) return false;
    if (raw.variable === path && raw.value === value) return true;
    for (const [operator, args] of Object.entries(raw)) {
      if (['==', '!=', 'in'].includes(operator) && Array.isArray(args)) {
        const [left, right] = args;
        if ((isVar(left) && matches(right)) || (isVar(right) && matches(left))) return true;
      }
    }
    return Object.values(raw).some(hit);
  };
  return workflow.nodes.filter((node) => hit(node.config ?? {})).map((node) => node.id);
}

function renameKey(record: unknown, from: string, to: string): unknown {
  if (!isRecord(record) || !(from in record)) return record;
  return Object.fromEntries(Object.entries(record).map(([key, value]) => [key === from ? to : key, value]));
}

/** Persona cases set and check conv values by bare name: their keys follow a rename too. */
function renameInPersonaCase(raw: unknown, from: string, to: string): unknown {
  if (!isRecord(raw)) return raw;
  const next: Record<string, unknown> = { ...raw };
  if (isRecord(raw.initial_state)) next.initial_state = { ...raw.initial_state, conv: renameKey(raw.initial_state.conv, from, to) };
  if (Array.isArray(raw.turns)) {
    next.turns = raw.turns.map((turn) => (isRecord(turn) && isRecord(turn.expect)
      ? { ...turn, expect: { ...turn.expect, conv: renameKey(turn.expect.conv, from, to) } }
      : turn));
  }
  return next;
}

/**
 * Renames `conv.<from>` to `conv.<to>`: the declaration, every reference in node configs (of every flow, when the
 * workflow is a chatflow of flows), and persona case keys.
 */
export function renameVariable(config: AgentConfig, from: string, to: string): AgentConfig {
  const oldPath = `conv.${from}`;
  const newPath = `conv.${to}`;
  const template = placeholder(oldPath);
  const rewrite = (text: string) => (text === oldPath ? newPath : text.replace(template, `{{${newPath}}}`));
  const renameNodes = (nodes: ChatflowNode[]) =>
    nodes.map((node) => (node.config ? { ...node, config: mapStrings(node.config, rewrite) as Record<string, unknown> } : node));
  const renameDeclared = (variables: ChatflowVariable[] | undefined) =>
    (variables ?? []).map((variable) => (variable.name === from ? { ...variable, name: to } : variable));
  let workflow: Chatflow | ChatflowWorkflow;
  if (isRenderableChatflow(config.workflow)) {
    const chat = config.workflow;
    workflow = { ...chat, variables: renameDeclared(chat.variables), flows: chat.flows.map((flow) => ({ ...flow, nodes: renameNodes(flow.nodes) })) };
  } else {
    const single = config.workflow as ChatflowWorkflow;
    workflow = { ...single, variables: renameDeclared(single.variables), nodes: renameNodes(single.nodes) };
  }
  const next: AgentConfig = { ...config, workflow };
  if (Array.isArray(config.persona_cases)) {
    next.persona_cases = config.persona_cases.map((item) => renameInPersonaCase(item, from, to));
  }
  return next;
}

/** Adds a declaration, or replaces the one named `previousName` (the same name when only its settings changed). */
export function upsertVariable(workflow: ChatflowWorkflow, variable: ChatflowVariable, previousName?: string): ChatflowWorkflow {
  const list = workflow.variables ?? [];
  const at = list.findIndex((item) => item.name === (previousName ?? variable.name));
  return { ...workflow, variables: at < 0 ? [...list, variable] : list.map((item, index) => (index === at ? variable : item)) };
}

/** Removes an unused declaration; a variable still read or written by a node cannot be removed. */
export function removeVariable(workflow: ChatflowWorkflow, name: string): ChatflowWorkflow {
  const used = variableUsage(workflow, name);
  if (used.length) throw new Error(`Biến conv.${name} đang dùng ở ${used.length} node: ${used.join(', ')}.`);
  return { ...workflow, variables: (workflow.variables ?? []).filter((item) => item.name !== name) };
}
