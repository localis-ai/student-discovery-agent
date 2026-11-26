import rules from '../../../../generated/chatflow-rules.json';

/**
 * Chatflow rules shared with the runtime (pnpm gen:api copies contracts/fixtures/chatflow-rules.json). The runtime
 * and this app each pin themselves to that file in a parity test, so a limit is changed there, never here.
 */
export const CHATFLOW_LIMITS = rules.limits;
export const CHATFLOW_IDENTIFIER_RE = new RegExp(rules.identifier_pattern);
export const RESERVED_NODE_IDS: ReadonlySet<string> = new Set(rules.reserved_node_ids);
export const RESERVED_FLOW_IDS: ReadonlySet<string> = new Set(rules.reserved_flow_ids);

export type BoundedConstraint = keyof typeof rules.variable_constraint_bounds;
export const CONSTRAINT_BOUNDS: Readonly<Record<BoundedConstraint, { minimum: number; maximum: number }>> =
  rules.variable_constraint_bounds;

/**
 * `{{namespace.path}}`: the runtime's grammar (agent_runtime/workflow/templates.py PLACEHOLDER). Every segment is
 * lower-case and starts with a letter; anything else is literal text at run time, so Studio must not offer it.
 */
export const PLACEHOLDER_RE = /\{\{\s*([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+)\s*\}\}/g;

/** Paths of the `{{…}}` placeholders in a text, in order, once each. */
export function placeholderPaths(text: string): string[] {
  return [...new Set(Array.from(text.matchAll(PLACEHOLDER_RE), (match) => match[1]!))];
}
