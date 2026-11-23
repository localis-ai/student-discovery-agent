import { describe, expect, it } from 'vitest';
import type { ChatflowWorkflow, NodeTypeCatalog } from '../../types';
import { handleLabel, nodeHandles } from './handles';
import { nodeSummary } from './summary';
import { readableVariables } from './variables';

describe('nodeSummary', () => {
  const ctx = {
    knowledgeBaseName: (id: string) => (id === 'kb1' ? 'Tuyển sinh 2026' : undefined),
    toolLabel: (name: string) => (name === 'assessment.start' ? 'Bắt đầu bài Holland' : undefined),
  };

  it('shows conditions and assignments as code, one clause per line', () => {
    expect(nodeSummary({ id: 'b', type: 'if_else', config: { condition: { '==': [{ var: 'conv.step' }, 'x'] } } }))
      .toEqual({ lines: [{ text: 'conv.step == "x"', code: true }], chips: [] });
    const assign = nodeSummary({
      id: 'a',
      type: 'assign',
      config: { assignments: [
        { variable: 'conv.step', value: 'done' }, { variable: 'conv.n', operation: 'add', value: 1 },
        { variable: 'conv.x', operation: 'clear' }, { variable: 'conv.y', value: 1 },
      ] },
    });
    expect(assign.lines.map((line) => line.text)).toEqual(['conv.step = "done"', 'conv.n += 1', 'xoá conv.x', '+1 phép gán']);
  });

  it('names knowledge bases and tools instead of ids', () => {
    expect(nodeSummary({ id: 'k', type: 'knowledge_retrieval', config: { knowledge_base_id: 'kb1', query: '{{sys.query}}' } }, ctx).lines)
      .toEqual([{ text: 'Tuyển sinh 2026', code: false }, { text: '{{sys.query}}', code: true }]);
    expect(nodeSummary({ id: 't', type: 'tool', config: { tool: 'assessment.start' } }, ctx).lines)
      .toEqual([{ text: 'Bắt đầu bài Holland', code: false }]);
  });

  it('turns side facts into chips', () => {
    expect(nodeSummary({ id: 'l', type: 'llm', config: { prompt: 'Bạn là bộ điều phối', output: 'json' } }))
      .toEqual({ lines: [{ text: 'Bạn là bộ điều phối', code: false }], chips: ['JSON'] });
    expect(nodeSummary({ id: 'r', type: 'answer', config: { text: 'Chào', blocks: [{}, {}] } }).chips).toEqual(['+2 block']);
    expect(nodeSummary({ id: 'c', type: 'intent_classifier', config: { labels: [{ id: 'a' }, { id: 'b' }, { id: 'c' }] } }).chips)
      .toEqual(['3 nhãn']);
  });

  it('warns about a node that cannot run yet', () => {
    expect(nodeSummary({ id: 'b', type: 'if_else' }).warning).toBe('Chưa có điều kiện');
    expect(nodeSummary({ id: 'r', type: 'answer' }).warning).toBe('Chưa có nội dung');
    expect(nodeSummary({ id: 'k', type: 'knowledge_retrieval' }).warning).toBe('Chưa chọn KB');
    expect(nodeSummary({ id: 't', type: 'tool' }).warning).toBe('Chưa chọn tool');
    expect(nodeSummary({ id: 'l', type: 'llm' }).warning).toBe('Chưa có prompt');
    expect(nodeSummary({ id: 'c', type: 'intent_classifier' }).warning).toBe('Chưa có nhãn');
    expect(nodeSummary({ id: 's', type: 'start' })).toEqual({ lines: [], chips: [] });
  });

  it('keeps an unknown knowledge base visible by id', () => {
    expect(nodeSummary({ id: 'k', type: 'knowledge_retrieval', config: { knowledge_base_id: 'zzz' } }, ctx).lines[0])
      .toEqual({ text: 'zzz', code: true });
  });
});

describe('nodeHandles', () => {
  it('lists static handles then config ones once, translating only static names', () => {
    const handles = nodeHandles(
      { id: 'c', type: 'intent_classifier', config: { labels: [{ id: 'tu_van' }, { id: 'other' }, { id: 'tu_van' }] } },
      { static: ['other', 'error'], from_config: { array: 'labels', id_field: 'id' } },
    );
    expect(handles.map((handle) => handle.id)).toEqual(['other', 'error', 'tu_van']);
    expect(handles.map(handleLabel)).toEqual(['Khác', 'Lỗi', 'tu_van']);
  });
});

describe('readableVariables', () => {
  it('offers static, conversation and upstream node variables only', () => {
    const catalog = {
      catalog_version: 't',
      namespaces: [
        { name: 'sys', title: 'Hệ thống', access: 'read_only', source: 'static', variables: [{ name: 'query', type: 'string' }] },
        { name: 'conv', title: 'Biến hội thoại', access: 'assign_only', source: 'workflow_variables' },
        { name: 'profile', title: 'Hồ sơ', access: 'read_only', source: 'profile_catalog' },
        { name: 'node', title: 'Output', access: 'read_only', source: 'node_output' },
      ],
      node_types: [
        { type: 'llm', title: 'LLM', description: '', config_schema: {}, handles: { static: ['success'] }, output_schema: { properties: { text: {} } } },
      ],
    } as unknown as NodeTypeCatalog;
    const workflow: ChatflowWorkflow = {
      entry: 'start',
      variables: [{ name: 'step', type: 'string', default: '' }],
      nodes: [{ id: 'start', type: 'start' }, { id: 'up', type: 'llm' }, { id: 'me', type: 'answer' }, { id: 'side', type: 'llm' }],
      edges: [
        { id: 'e1', source: 'start', source_handle: 'next', target: 'up' },
        { id: 'e2', source: 'up', source_handle: 'success', target: 'me' },
      ],
    };
    const groups = readableVariables(workflow, catalog, 'me');
    expect(groups[0]!.items[0]).toMatchObject({ path: 'sys.query', type: 'string' });
    expect(groups.map((group) => ({ title: group.title, paths: group.items.map((item) => item.path) }))).toEqual([
      { title: 'Hệ thống', paths: ['sys.query'] },
      { title: 'Biến hội thoại', paths: ['conv.step'] },
      { title: 'Output', paths: ['up.text'] },
    ]);
  });
});
