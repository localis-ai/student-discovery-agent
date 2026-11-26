import type { ChatflowNode, ChatflowWorkflow, NodeTypeCatalog } from '../../types';
import { schemaToFields } from './json-fields';
import { placeholderPaths } from './rules';

/** Output and input types as Studio shows them: variable types plus the shapes node outputs can have. */
export type IoType = 'string' | 'number' | 'boolean' | 'enum' | 'string_list' | 'object' | 'array';

export interface NodeOutput {
  path: string;
  field: string;
  type?: IoType;
  /** Fixed values the output can take (e.g. error_type), empty string left out. */
  values?: string[];
}

export interface InputSource {
  path: string;
  kind: 'system' | 'conv' | 'profile' | 'node' | 'unknown';
  /** Where the value comes from: a namespace title, the start node (conv.*) or the producing node. */
  source: string;
  field: string;
  type?: IoType;
  description?: string;
  nodeId?: string;
  nodeType?: string;
}


function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

/** Variable paths a node reads: `{{…}}` placeholders, `var`/`missing` operands and filter_from_vars, in order, once. */
export function nodeInputs(node: ChatflowNode): string[] {
  const found = new Set<string>();
  const walk = (value: unknown): void => {
    if (typeof value === 'string') {
      for (const path of placeholderPaths(value)) found.add(path);
    } else if (Array.isArray(value)) {
      value.forEach(walk);
    } else if (isRecord(value)) {
      for (const [name, item] of Object.entries(value)) {
        if (name === 'var') {
          const path = Array.isArray(item) ? item[0] : item;
          if (typeof path === 'string') found.add(path);
        } else if (name === 'missing' && Array.isArray(item)) {
          item.forEach((path) => { if (typeof path === 'string') found.add(path); });
        } else if (name === 'filter_from_vars' && isRecord(item)) {
          Object.values(item).forEach((path) => { if (typeof path === 'string') found.add(path); });
        } else {
          walk(item);
        }
      }
    }
  };
  for (const [name, value] of Object.entries(node.config ?? {})) {
    if (name === 'assignments' && Array.isArray(value)) {
      // An assignment target is written, not read: only its value counts as an input.
      value.forEach((item) => { if (isRecord(item)) walk(item.value); });
    } else {
      walk({ [name]: value });
    }
  }
  return [...found];
}

function schemaType(schema: unknown): IoType | undefined {
  if (!isRecord(schema)) return undefined;
  if (schema.type === 'array') return isRecord(schema.items) && schema.items.type === 'string' ? 'string_list' : 'array';
  if (schema.type === 'integer') return 'number';
  return typeof schema.type === 'string' ? (schema.type as IoType) : undefined;
}

/** What a node makes available to later nodes, as readable paths with their types. */
export function nodeOutputs(node: ChatflowNode, catalog: NodeTypeCatalog | undefined): NodeOutput[] {
  if (node.type === 'assign') {
    const written = new Set<string>();
    for (const item of Array.isArray(node.config?.assignments) ? node.config.assignments : []) {
      if (isRecord(item) && typeof item.variable === 'string') written.add(item.variable);
    }
    return [...written].map((path) => ({ path, field: path.split('.').slice(1).join('.') }));
  }
  const spec = catalog?.node_types.find((item) => item.type === node.type);
  const properties = (spec?.output_schema as { properties?: Record<string, unknown> } | undefined)?.properties ?? {};
  const outputs: NodeOutput[] = [];
  for (const [field, schema] of Object.entries(properties)) {
    if (node.type === 'llm' && field === 'json') {
      if (node.config?.output !== 'json') continue;
      const { editable, fields } = schemaToFields(node.config?.json_schema);
      if (editable && fields.length) {
        for (const item of fields) outputs.push({ path: `${node.id}.json.${item.name}`, field: `json.${item.name}`, type: item.type });
        continue;
      }
    }
    const listed = isRecord(schema) && Array.isArray(schema.enum)
      ? schema.enum.filter((value): value is string => typeof value === 'string' && value !== '')
      : [];
    outputs.push({ path: `${node.id}.${field}`, field, type: schemaType(schema), ...(listed.length ? { values: listed } : {}) });
  }
  return outputs;
}

/** Where an input path comes from, for the chip that names its source. */
export function describeInput(path: string, workflow: ChatflowWorkflow, catalog: NodeTypeCatalog | undefined): InputSource {
  const [head = '', ...rest] = path.split('.');
  const field = rest.join('.');
  const namespace = catalog?.namespaces.find((space) => space.name === head);
  if (head === 'conv') {
    const variable = workflow.variables?.find((item) => item.name === field);
    const start = workflow.nodes.find((node) => node.id === workflow.entry);
    return {
      path, kind: 'conv', field, type: variable?.type, description: variable?.description,
      source: start?.title?.trim() || 'Bắt đầu', nodeId: workflow.entry, nodeType: start?.type,
    };
  }
  if (head === 'profile') return { path, kind: 'profile', field, source: namespace?.title ?? 'Hồ sơ học sinh' };
  if (namespace && (head === 'sys' || head === 'result')) {
    const variable = namespace.variables?.find((item) => item.name === field);
    return { path, kind: 'system', field, type: variable?.type, description: variable?.description, source: namespace.title };
  }
  const producer = workflow.nodes.find((node) => node.id === head);
  if (producer) {
    const typeTitle = catalog?.node_types.find((item) => item.type === producer.type)?.title;
    const output = nodeOutputs(producer, catalog).find((item) => item.path === path);
    return {
      path, kind: 'node', field, type: output?.type, nodeId: producer.id, nodeType: producer.type,
      source: producer.title?.trim() || typeTitle || producer.id,
    };
  }
  return { path, kind: 'unknown', field: path, source: '?' };
}
