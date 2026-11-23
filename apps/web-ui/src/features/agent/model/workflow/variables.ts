import type { ChatflowWorkflow, NodeTypeCatalog, VariableConstraints, VariableType } from '../../types';

/** One readable variable as pickers show it: the standard path, plus what Studio knows about its type and meaning. */
export interface VariableInfo {
  path: string;
  type?: VariableType;
  description?: string;
  values?: string[];
  constraints?: VariableConstraints;
}

export interface VariableGroup {
  title: string;
  items: VariableInfo[];
}

const OUTPUT_TYPES: ReadonlySet<string> = new Set(['string', 'number', 'boolean']);

function ancestors(workflow: ChatflowWorkflow, nodeId: string): Set<string> {
  const parents = new Map<string, string[]>();
  for (const edge of workflow.edges ?? []) {
    parents.set(edge.target, [...(parents.get(edge.target) ?? []), edge.source]);
  }
  const found = new Set<string>();
  const queue = [...(parents.get(nodeId) ?? [])];
  while (queue.length) {
    const id = queue.shift()!;
    if (found.has(id) || id === nodeId) continue;
    found.add(id);
    queue.push(...(parents.get(id) ?? []));
  }
  return found;
}

/**
 * Variables a node can read, grouped by namespace, for pickers. Node outputs come only from nodes that can run
 * before it (its ancestors), as `<node_id>.<field>`; profile fields are not listed by the catalog and are typed by hand.
 */
export function readableVariables(
  workflow: ChatflowWorkflow,
  catalog: NodeTypeCatalog | undefined,
  nodeId: string,
): VariableGroup[] {
  const groups: VariableGroup[] = [];
  for (const namespace of catalog?.namespaces ?? []) {
    let items: VariableInfo[] = [];
    if (namespace.source === 'static') {
      items = (namespace.variables ?? []).map((variable) => ({
        path: `${namespace.name}.${variable.name}`,
        type: variable.type,
        description: variable.description,
        values: variable.values,
      }));
    } else if (namespace.source === 'workflow_variables') {
      items = (workflow.variables ?? []).map((variable) => ({
        path: `${namespace.name}.${variable.name}`,
        type: variable.type,
        description: variable.description,
        values: variable.values,
        constraints: variable.constraints,
      }));
    } else if (namespace.source === 'node_output') {
      const upstream = ancestors(workflow, nodeId);
      for (const node of workflow.nodes) {
        if (!upstream.has(node.id)) continue;
        const spec = catalog?.node_types.find((item) => item.type === node.type);
        const properties = (spec?.output_schema as { properties?: Record<string, { type?: unknown; enum?: unknown }> } | undefined)
          ?.properties ?? {};
        for (const [field, schema] of Object.entries(properties)) {
          const values = Array.isArray(schema?.enum)
            ? schema.enum.filter((value): value is string => typeof value === 'string' && value !== '')
            : undefined;
          items.push({
            path: `${node.id}.${field}`,
            type: typeof schema?.type === 'string' && OUTPUT_TYPES.has(schema.type) ? (schema.type as VariableType) : undefined,
            description: node.title ? `Output của "${node.title}"` : undefined,
            values: values?.length ? values : undefined,
          });
        }
      }
    }
    if (items.length) groups.push({ title: namespace.title, items });
  }
  return groups;
}

export function findVariable(groups: readonly VariableGroup[], path: string): VariableInfo | undefined {
  for (const group of groups) {
    const found = group.items.find((item) => item.path === path);
    if (found) return found;
  }
  return undefined;
}
