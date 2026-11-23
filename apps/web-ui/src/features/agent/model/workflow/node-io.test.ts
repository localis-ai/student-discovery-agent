import { describe, expect, it } from 'vitest';
import type { ChatflowWorkflow, NodeTypeCatalog } from '../../types';
import { describeInput, nodeInputs, nodeOutputs } from './node-io';

const catalog = {
  catalog_version: 't',
  namespaces: [
    { name: 'sys', title: 'Hệ thống', access: 'read_only', source: 'static', variables: [{ name: 'query', type: 'string', description: 'Câu vừa gõ' }] },
    { name: 'conv', title: 'Biến hội thoại', access: 'assign_only', source: 'workflow_variables' },
    { name: 'profile', title: 'Hồ sơ học sinh', access: 'read_only', source: 'profile_catalog' },
    { name: 'result', title: 'Kết quả đánh giá', access: 'read_only', source: 'static', variables: [{ name: 'house_id', type: 'string' }] },
    { name: 'node', title: 'Output', access: 'read_only', source: 'node_output' },
  ],
  node_types: [
    { type: 'start', title: 'Bắt đầu', description: '', config_schema: {}, handles: { static: ['next'] }, output_schema: {} },
    { type: 'llm', title: 'Gọi LLM', description: '', config_schema: {}, handles: { static: ['success'] },
      output_schema: { properties: { text: { type: 'string' }, json: { type: 'object' }, error_type: { type: 'string' } } } },
    { type: 'intent_classifier', title: 'Phân loại ý định', description: '', config_schema: {}, handles: { static: ['other'] },
      output_schema: { properties: { label: { type: 'string' } } } },
  ],
} as unknown as NodeTypeCatalog;

const workflow: ChatflowWorkflow = {
  entry: 'start',
  variables: [{ name: 'stage', type: 'enum', values: ['a'], default: 'a', description: 'Giai đoạn' }],
  nodes: [
    { id: 'start', type: 'start', title: 'Bắt đầu lượt chat' },
    { id: 'classify', type: 'intent_classifier', title: 'Hiểu ý', config: { input: '{{sys.query}}' } },
    { id: 'gen', type: 'llm', title: 'Soạn', config: { prompt: 'Ý: {{ classify.label }}, giai đoạn {{conv.stage}}, nhà {{result.house_id}}', output: 'json',
      json_schema: { type: 'object', properties: { stage: { type: 'string' }, majors: { type: 'array', items: { type: 'string' } } }, required: ['stage'] } } },
    { id: 'gate', type: 'if_else', config: { condition: { and: [{ '==': [{ var: 'gen.json.stage' }, 'x'] }, { missing: ['profile.grade'] }] } } },
    { id: 'set', type: 'assign', config: { assignments: [{ variable: 'conv.stage', value: { var: 'gen.json.stage' } }] } },
    { id: 'kb', type: 'knowledge_retrieval', config: { query: 'q', filter_from_vars: { major: 'conv.stage' } } },
  ],
  edges: [],
};
const node = (id: string) => workflow.nodes.find((item) => item.id === id)!;

describe('nodeInputs', () => {
  it('collects every variable a node reads, in order and once', () => {
    expect(nodeInputs(node('classify'))).toEqual(['sys.query']);
    expect(nodeInputs(node('gen'))).toEqual(['classify.label', 'conv.stage', 'result.house_id']);
    expect(nodeInputs(node('gate'))).toEqual(['gen.json.stage', 'profile.grade']);
    expect(nodeInputs(node('kb'))).toEqual(['conv.stage']);
  });

  it('counts an assignment target as written, not read', () => {
    expect(nodeInputs(node('set'))).toEqual(['gen.json.stage']);
  });
});

describe('describeInput', () => {
  it('names where a variable comes from', () => {
    expect(describeInput('sys.query', workflow, catalog)).toMatchObject({ kind: 'system', source: 'Hệ thống', field: 'query', type: 'string' });
    expect(describeInput('conv.stage', workflow, catalog)).toMatchObject({ kind: 'conv', source: 'Bắt đầu lượt chat', field: 'stage', type: 'enum', nodeId: 'start' });
    expect(describeInput('profile.grade', workflow, catalog)).toMatchObject({ kind: 'profile', source: 'Hồ sơ học sinh', field: 'grade' });
    expect(describeInput('classify.label', workflow, catalog)).toMatchObject({ kind: 'node', source: 'Hiểu ý', field: 'label', type: 'string', nodeId: 'classify', nodeType: 'intent_classifier' });
    expect(describeInput('gen.json.stage', workflow, catalog)).toMatchObject({ kind: 'node', field: 'json.stage', type: 'string', nodeId: 'gen' });
    expect(describeInput('ghost.x', workflow, catalog)).toMatchObject({ kind: 'unknown', field: 'ghost.x' });
  });
});

describe('nodeOutputs', () => {
  it('lists catalog outputs, the JSON fields of a JSON llm and the variables an assign writes', () => {
    expect(nodeOutputs(node('classify'), catalog).map((o) => `${o.path}:${o.type}`)).toEqual(['classify.label:string']);
    expect(nodeOutputs(node('gen'), catalog).map((o) => `${o.path}:${o.type}`)).toEqual([
      'gen.text:string', 'gen.json.stage:string', 'gen.json.majors:string_list', 'gen.error_type:string',
    ]);
    expect(nodeOutputs(node('set'), catalog).map((o) => o.path)).toEqual(['conv.stage']);
    expect(nodeOutputs(node('start'), catalog)).toEqual([]);
  });
});
