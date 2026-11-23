import { describe, expect, it } from 'vitest';
import { findWorkflowIssueRange, issuesForFlow, parseChatflowIssuePath, parseWorkflowIssuePath, workflowIssueKey, workflowIssueLabel } from './issue-path';
import type { Chatflow, ChatflowWorkflow } from '../../types';

const workflow: ChatflowWorkflow = {
  entry: 'start',
  variables: [{ name: 'grade', type: 'string', default: '12' }],
  nodes: [
    { id: 'start', type: 'start', config: {} },
    { id: 'classify', type: 'if_else', config: { labels: ['yes', 'no'] } },
  ],
  edges: [{ id: 'edge_true', source: 'classify', source_handle: 'true', target: 'answer' }],
};

describe('parseWorkflowIssuePath', () => {
  it('resolves a node config path to the node id', () => {
    expect(parseWorkflowIssuePath('workflow.nodes[1].config.labels[0]', workflow)).toEqual({
      kind: 'node',
      nodeId: 'classify',
      nodeIndex: 1,
      configPath: ['labels', 0],
    });
  });

  it('resolves edges and variables', () => {
    expect(parseWorkflowIssuePath('workflow.edges[0].target', workflow)).toEqual({
      kind: 'edge',
      edgeId: 'edge_true',
      edgeIndex: 0,
      configPath: ['target'],
    });
    expect(parseWorkflowIssuePath('workflow.variables[0].default', workflow)).toEqual({
      kind: 'variable',
      variableIndex: 0,
      variableName: 'grade',
      configPath: ['default'],
    });
  });

  it('resolves workflow-level paths', () => {
    expect(parseWorkflowIssuePath('workflow.entry', workflow)).toEqual({
      kind: 'workflow',
      configPath: ['entry'],
    });
    expect(parseWorkflowIssuePath('workflow.budget.max_nodes', workflow)).toEqual({
      kind: 'workflow',
      configPath: ['budget', 'max_nodes'],
    });
    expect(parseWorkflowIssuePath('workflow.nodes', workflow)).toEqual({ kind: 'workflow' });
  });

  it('resolves bare node paths without config', () => {
    expect(parseWorkflowIssuePath('workflow.nodes[0]', workflow)).toEqual({
      kind: 'node',
      nodeId: 'start',
      nodeIndex: 0,
      configPath: [],
    });
  });

  it('falls back to workflow for malformed or out-of-range paths', () => {
    for (const path of [
      'agent.nodes[0]',
      'workflow.nodes[4].config.x',
      'workflow.edges[2]',
      'workflow.variables[2]',
      'workflow.nodes[x]',
    ]) {
      expect(parseWorkflowIssuePath(path, workflow)).toEqual({ kind: 'workflow' });
    }
    const partial = {
      entry: 'start',
      nodes: [{ type: 'start' }],
      edges: [{ source: 'start' }],
    } as unknown as ChatflowWorkflow;
    expect(parseWorkflowIssuePath('workflow.nodes[0].config', partial)).toEqual({
      kind: 'workflow',
    });
    expect(parseWorkflowIssuePath('workflow.edges[0].target', partial)).toEqual({
      kind: 'workflow',
    });
  });
});

describe('workflowIssueLabel & workflowIssueKey', () => {
  it('names and keys targets for grouping the issue list', () => {
    const nodeTarget = parseWorkflowIssuePath('workflow.nodes[1].config.x', workflow);
    expect(workflowIssueLabel(nodeTarget)).toBe('node classify');
    expect(workflowIssueKey(nodeTarget)).toBe('node:classify');
    expect(workflowIssueLabel({ kind: 'workflow' })).toBe('toàn bộ workflow');
    expect(workflowIssueKey({ kind: 'workflow' })).toBe('workflow');
  });
});

describe('findWorkflowIssueRange', () => {
  it('highlights the config property inside the matching node even when config precedes id', () => {
    const wfWithConfigFirst = {
      entry: 'start',
      nodes: [
        { id: 'start', type: 'start', config: { labels: ['ignored'] } },
        { config: { labels: ['hoc_phi'] }, id: 'classify', type: 'if_else' },
      ],
      edges: [{ id: 'e1', source: 'start', source_handle: 'next', target: 'classify' }],
    } as unknown as ChatflowWorkflow;
    const text = JSON.stringify(wfWithConfigFirst, null, 2);
    const target = parseWorkflowIssuePath('workflow.nodes[1].config.labels[0]', wfWithConfigFirst);
    const range = findWorkflowIssueRange(text, target);
    expect(range).not.toBeNull();
    const selected = text.slice(range!.start, range!.end);
    expect(selected).toContain('"labels"');
    expect(range!.start).toBeGreaterThan(text.indexOf('"start"'));
  });

  it('falls back to the node id line when configPath is absent and highlights entry/edge targets', () => {
    const text = JSON.stringify(workflow, null, 2);
    const nodeRange = findWorkflowIssueRange(text, parseWorkflowIssuePath('workflow.nodes[1]', workflow));
    expect(text.slice(nodeRange!.start, nodeRange!.end)).toContain('"id": "classify"');

    const edgeRange = findWorkflowIssueRange(text, parseWorkflowIssuePath('workflow.edges[0].target', workflow));
    expect(text.slice(edgeRange!.start, edgeRange!.end)).toContain('"target": "answer"');

    const entryRange = findWorkflowIssueRange(text, parseWorkflowIssuePath('workflow.entry', workflow));
    expect(text.slice(entryRange!.start, entryRange!.end)).toContain('"entry": "start"');

    const missingRange = findWorkflowIssueRange(text, { kind: 'workflow' });
    expect(missingRange).toBeNull();
  });
});

describe('parseChatflowIssuePath', () => {
  const chat: Chatflow = {
    variables: [{ name: 'grade', type: 'string', default: '12' }],
    router: { default_flow: 'main' },
    flows: [
      { id: 'main', title: 'Chính', entry: 'start', nodes: [{ id: 'start', type: 'start' }] },
      { id: 'fee', title: 'Học phí', entry: 'fee_start', nodes: [{ id: 'fee_start', type: 'start' }, { id: 'go', type: 'goto_flow', config: { flow: 'x' } }],
        edges: [{ id: 'e1', source: 'fee_start', source_handle: 'next', target: 'go' }] },
    ],
  };

  it('resolves nodes and edges inside a flow and names the flow', () => {
    expect(parseChatflowIssuePath('workflow.flows[1].nodes[1].config.flow', chat)).toEqual({
      kind: 'node', nodeId: 'go', nodeIndex: 1, configPath: ['flow'], flowId: 'fee',
    });
    expect(parseChatflowIssuePath('workflow.flows[1].edges[0]', chat)).toMatchObject({ kind: 'edge', edgeId: 'e1', flowId: 'fee' });
  });

  it('resolves flow fields, the router and shared variables', () => {
    expect(parseChatflowIssuePath('workflow.flows[1].description', chat)).toEqual({
      kind: 'flow', flowId: 'fee', flowIndex: 1, flowTitle: 'Học phí', configPath: ['description'],
    });
    expect(parseChatflowIssuePath('workflow.router.default_flow', chat)).toEqual({ kind: 'workflow', configPath: ['router', 'default_flow'] });
    expect(parseChatflowIssuePath('workflow.variables[0]', chat)).toMatchObject({ kind: 'variable', variableName: 'grade' });
    expect(parseChatflowIssuePath('workflow.flows[9].nodes[0]', chat)).toEqual({ kind: 'workflow' });
    expect(workflowIssueLabel(parseChatflowIssuePath('workflow.flows[0]', chat))).toBe('nghiệp vụ Chính');
  });

  it('keeps one flow\'s issues with paths the canvas understands', () => {
    const issues = [
      { path: 'workflow.flows[1].nodes[1]', code: 'workflow_goto_invalid', message: 'x' },
      { path: 'workflow.flows[0].nodes[0]', code: 'y', message: 'y' },
      { path: 'workflow.variables[0]', code: 'z', message: 'z' },
    ];
    expect(issuesForFlow(issues, chat, 'fee')).toEqual([{ path: 'workflow.nodes[1]', code: 'workflow_goto_invalid', message: 'x' }]);
  });
});
