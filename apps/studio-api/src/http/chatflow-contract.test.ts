import { readFileSync, readdirSync } from 'node:fs';
import { resolve, relative, join } from 'node:path';
import { describe, it, expect } from 'vitest';
import Ajv from 'ajv';
import { parse } from 'yaml';

const root = resolve(__dirname, '../../../../contracts');
const fixture = (name: string) => JSON.parse(readFileSync(join(root, 'fixtures', name), 'utf8').replace(/^﻿/, ''));
const NODE_TYPES = ['start', 'if_else', 'intent_classifier', 'llm', 'agent', 'knowledge_retrieval',
  'tool', 'profile_propose', 'assign', 'answer', 'goto_flow'];

function contractAjv() {
  const ajv = new Ajv({ strict: false, allErrors: true });
  ajv.addFormat('date-time', true);
  for (const format of ['normalized-display-name', 'display-name']) ajv.addFormat(format, true);
  const register = (directory: string) => {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const path = join(directory, entry.name);
      if (entry.isDirectory()) register(path);
      else if (entry.name.endsWith('.yaml')) {
        const id = `https://contracts.local/${relative(root, path).replaceAll('\\', '/')}`;
        ajv.addSchema({ ...parse(readFileSync(path, 'utf8')), $id: id });
      }
    }
  };
  register(join(root, 'openapi'));
  return ajv;
}
function validator(file: string, name: string) {
  return contractAjv().compile({ $ref: `https://contracts.local/openapi/${file}#/components/schemas/${name}` });
}

describe('chatflow snapshot contract parity', () => {
  const minimal = fixture('agent-snapshot-chatflow-min.json');
  const validate = validator('schemas/session-lifecycle.yaml', 'AgentSnapshotV1');

  it('accepts the minimal chatflow fixture and the legacy demo fixture', () => {
    expect(validate(minimal), JSON.stringify(validate.errors)).toBe(true);
    expect(validate(fixture('agent-snapshot-demo.json')), JSON.stringify(validate.errors)).toBe(true);
  });

  it('accepts node descriptions and described, constrained variables', () => {
    const content = structuredClone(minimal);
    content.workflow.flows[0].nodes[0].description = 'Điểm vào';
    content.workflow.variables = [
      { name: 'score', description: 'Điểm tạm', type: 'number', default: 0, constraints: { minimum: 0, maximum: 10, integer: true } },
      { name: 'tags', type: 'string_list', default: [], constraints: { max_items: 3, item_max_length: 20 } },
    ];
    expect(validate(content), JSON.stringify(validate.errors)).toBe(true);
  });

  it('rejects an unknown constraint key', () => {
    const content = structuredClone(minimal);
    content.workflow.variables = [{ name: 's', type: 'string', default: '', constraints: { pattern: 'a' } }];
    expect(validate(content)).toBe(false);
  });

  const flow = minimal.workflow.flows[0];
  const withNodes = (nodes: unknown[]) => ({ ...minimal, workflow: { ...minimal.workflow, flows: [{ ...flow, nodes }] } });
  const node = (patch: Record<string, unknown>) => ({ ...flow.nodes[1], ...patch });

  it('accepts two flows with a router and rejects eleven flows or 61 variables', () => {
    const content = structuredClone(minimal);
    const second = structuredClone(content.workflow.flows[0]);
    second.id = 'hoc_phi';
    second.title = 'Học phí';
    second.description = 'Học sinh hỏi học phí';
    second.examples = ['học phí bao nhiêu'];
    second.trigger = { '==': [{ var: 'sys.interaction_outcome' }, 'assessment_completed'] };
    second.nodes = second.nodes.map((item: { id: string }) => ({ ...item, id: `hp_${item.id}` }));
    second.entry = `hp_${second.entry}`;
    second.edges = second.edges.map((item: Record<string, string>) => ({ ...item, source: `hp_${item.source}`, target: `hp_${item.target}` }));
    content.workflow.flows.push(second);
    content.workflow.router = { default_flow: 'main', history_messages: 2, instructions: 'Ưu tiên học phí' };
    expect(validate(content), JSON.stringify(validate.errors)).toBe(true);
    expect(validate({ ...content, workflow: { ...content.workflow, flows: Array.from({ length: 11 }, () => second) } })).toBe(false);
    const variables = Array.from({ length: 61 }, (_, i) => ({ name: `v${i}`, type: 'string', default: '' }));
    expect(validate({ ...content, workflow: { ...content.workflow, variables } })).toBe(false);
  });

  it('accepts a goto_flow node and rejects a flow without a router', () => {
    const content = structuredClone(minimal);
    content.workflow.flows[0].nodes.push({ id: 'go', type: 'goto_flow', config: { flow: 'main' } });
    expect(validate(content), JSON.stringify(validate.errors)).toBe(true);
    delete content.workflow.router;
    expect(validate(content)).toBe(false);
  });
  it.each([
    ['unknown mode', { ...minimal, mode: 'graph' }],
    ['code node', withNodes([node({ type: 'code' })])],
    ['http node', withNodes([node({ type: 'http' })])],
    ['id with uppercase', withNodes([node({ id: 'Bad-Id' })])],
    ['51 nodes', withNodes(Array.from({ length: 51 }, (_, i) => ({ id: `n${i}`, type: 'start' })))],
    ['unknown node field', withNodes([node({ extra: 'x' })])],
    ['zero budget', { ...minimal, workflow: { ...minimal.workflow, budget: { ...minimal.workflow.budget, max_nodes: 0 } } }],
    ['persona case without turns', { ...minimal, persona_cases: [{ ...minimal.persona_cases[0], turns: [] }] }],
  ])('rejects %s', (_label, content) => {
    expect(validate(content)).toBe(false);
  });
});

describe('workflow node-type catalog contract', () => {
  const catalog = fixture('workflow-node-types.json');
  const validate = validator('schemas/chatflow-authoring.yaml', 'WorkflowNodeTypeCatalog');
  const minimal = fixture('agent-snapshot-chatflow-min.json');

  it('matches the schema and covers exactly the authorable node types', () => {
    expect(validate(catalog), JSON.stringify(validate.errors)).toBe(true);
    expect(catalog.node_types.map((t: { type: string }) => t.type).sort()).toEqual([...NODE_TYPES].sort());
  });

  it('keeps the node type enum of the snapshot schema in step with the catalog', () => {
    const snapshotSchema = parse(readFileSync(join(root, 'openapi/schemas/chatflow.yaml'), 'utf8'));
    expect([...snapshotSchema.components.schemas.ChatflowNodeType.enum].sort()).toEqual([...NODE_TYPES].sort());
  });

  it('publishes a compilable config JSON Schema for every node type', () => {
    for (const nodeType of catalog.node_types) {
      expect(() => new Ajv({ strict: false }).compile(nodeType.config_schema), nodeType.type).not.toThrow();
      expect(() => new Ajv({ strict: false }).compile(nodeType.output_schema), nodeType.type).not.toThrow();
    }
  });

  it('accepts the config of every node in the minimal chatflow fixture', () => {
    for (const node of minimal.workflow.flows[0].nodes) {
      const entry = catalog.node_types.find((t: { type: string }) => t.type === node.type);
      const check = new Ajv({ strict: false }).compile(entry.config_schema);
      expect(check(node.config ?? {}), `${node.id}: ${JSON.stringify(check.errors)}`).toBe(true);
    }
  });

  it('rejects a catalog that misses a required node type field', () => {
    const broken = structuredClone(catalog);
    delete broken.node_types[0].config_schema;
    expect(validate(broken)).toBe(false);
  });

  it('declares handles for the classifier from its labels', () => {
    const classifier = catalog.node_types.find((t: { type: string }) => t.type === 'intent_classifier');
    expect(classifier.handles).toEqual({ static: ['other', 'error'], from_config: { array: 'labels', id_field: 'id' } });
  });
});

describe('workflow debug run contract', () => {
  const example = fixture('workflow-debug-run.json');
  const request = validator('schemas/chatflow-authoring.yaml', 'WorkflowDebugRunRequest');
  const result = validator('schemas/chatflow-authoring.yaml', 'WorkflowDebugRunResult');
  const streamEvent = validator('schemas/chatflow-authoring.yaml', 'WorkflowDebugStreamEvent');

  it('accepts the example request and result', () => {
    expect(request(example.request), JSON.stringify(request.errors)).toBe(true);
    expect(result(example.result), JSON.stringify(result.errors)).toBe(true);
  });

  it('accepts a route-only request and a routed result with a router node run', () => {
    expect(request({ ...example.request, stop_after: 'route' }), JSON.stringify(request.errors)).toBe(true);
    expect(request({ ...example.request, stop_after: 'all' })).toBe(false);
    const routed = structuredClone(example.result);
    routed.path = ['router'];
    routed.node_runs = [{ ...routed.node_runs[0], node_id: 'router', type: 'router', flow_id: null, handle: 'main' }];
    routed.route = { flow: 'main', method: 'classifier', label: 'main' };
    expect(result(routed), JSON.stringify(result.errors)).toBe(true);
    expect(result({ ...routed, route: { flow: 'main', method: 'guess' } })).toBe(false);
    expect(streamEvent({ event: 'workflow.node_started', node_id: 'router', type: 'router', order: 1 })).toBe(true);
  });

  it('requires exactly one of message and interaction', () => {
    expect(request({ state: example.request.state })).toBe(false);
    expect(request({ ...example.request, interaction: { action: 'confirm_answer' } })).toBe(false);
    const rest = structuredClone(example.request);
    delete rest.message;
    expect(request({ ...rest, interaction: { action: 'confirm_answer' } })).toBe(true);
  });

  it('matches the interaction shape Studio and the runtime parse', () => {
    const rest = structuredClone(example.request);
    delete rest.message;
    expect(request({ ...rest, interaction: { action: 'submit_answer', outcome: 'answered', option_id: 'opt_1' } })).toBe(true);
    expect(request({ ...rest, interaction: { name: 'confirm_answer' } })).toBe(false);
    expect(request({ ...rest, interaction: { action: 'confirm_answer', name: 'x' } })).toBe(false);
    expect(request({ ...rest, interaction: { action: '' } })).toBe(false);
  });

  it('rejects fields outside the contract', () => {
    expect(request({ ...example.request, conversation_id: 'conv_1' })).toBe(false);
  });

  it('accepts every stream event of the example and nothing unknown', () => {
    for (const event of example.stream) {
      expect(streamEvent(event), `${event.event}: ${JSON.stringify(streamEvent.errors)}`).toBe(true);
    }
    expect(streamEvent({ event: 'workflow.node_exploded' })).toBe(false);
  });

  it('keeps the stream path equal to the result path', () => {
    const started = example.stream.filter((e: { event: string }) => e.event === 'workflow.node_started')
      .map((e: { node_id: string }) => e.node_id);
    expect(started).toEqual(example.result.path);
  });

  it('rejects a result that has no expiry', () => {
    const broken = structuredClone(example.result);
    delete broken.expires_at;
    expect(result(broken)).toBe(false);
  });

  it('validates a completed event only when it carries the result', () => {
    expect(streamEvent({ event: 'completed', result: example.result }), JSON.stringify(streamEvent.errors)).toBe(true);
    expect(streamEvent({ event: 'completed' })).toBe(false);
  });

  it('rejects a well-formed node_started with an unknown event name', () => {
    expect(streamEvent({ event: 'workflow.node_exploded', node_id: 'start', type: 'start', order: 1 })).toBe(false);
  });

  it('rejects a node_started whose started_at is not a string', () => {
    const started = example.stream[0];
    expect(streamEvent({ ...started, started_at: '2026-11-10T08:00:00Z' }), JSON.stringify(streamEvent.errors)).toBe(true);
    expect(streamEvent({ ...started, started_at: 5 })).toBe(false);
  });

  it('carries tokens and error on node_finished', () => {
    const finished = example.stream.find((e: { event: string }) => e.event === 'workflow.node_finished');
    expect(streamEvent(finished), JSON.stringify(streamEvent.errors)).toBe(true);
    expect(finished.tokens).toEqual({ input: 0, output: 0 });
    expect(streamEvent({ ...finished, tokens: { input: -1, output: 0 } })).toBe(false);
  });
});
