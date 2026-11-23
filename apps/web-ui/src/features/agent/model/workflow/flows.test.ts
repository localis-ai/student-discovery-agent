import { describe, expect, it } from 'vitest';
import type { Chatflow } from '../../types';
import { generateNodeId } from './edit';
import { removeVariable, renameVariable, triggerUsage } from './variable-usage';
import {
  addFlow, allFlowsView, allNodeIds, flowOfNode, flowRemovalBlockers, flowView, gotoLinks, isRenderableChatflow, moveFlow,
  removeFlow, setDefaultFlow, updateFlow, updateRouter, withFlowView,
} from './flows';

const chat: Chatflow = {
  variables: [{ name: 'stage', type: 'string', default: '' }],
  router: { default_flow: 'main' },
  flows: [
    {
      id: 'main', title: 'Chính', description: 'mọi thứ', entry: 'start',
      nodes: [{ id: 'start', type: 'start' }, { id: 'go', type: 'goto_flow', config: { flow: 'fee' } }],
      edges: [{ id: 'e1', source: 'start', source_handle: 'next', target: 'go' }],
    },
    { id: 'fee', title: 'Học phí', description: 'học phí', entry: 'fee_start', nodes: [{ id: 'fee_start', type: 'start' }] },
  ],
};

describe('flow lens', () => {
  it('recognises a renderable chatflow', () => {
    expect(isRenderableChatflow(chat)).toBe(true);
    expect(isRenderableChatflow({ entry: 'start', nodes: [] })).toBe(false);
    expect(isRenderableChatflow({ router: {}, flows: [{ id: 'a', nodes: [null] }] })).toBe(false);
  });

  it('views one flow with the shared variables and the other flows ids as taken', () => {
    const view = flowView(chat, 'fee');
    expect(view.entry).toBe('fee_start');
    expect(view.variables).toEqual(chat.variables);
    expect(view.takenNodeIds).toEqual(['start', 'go']);
    expect(flowView(chat, 'missing').entry).toBe('start');
  });

  it('writes a view back: the graph to its flow, variables up, takenNodeIds dropped', () => {
    const view = flowView(chat, 'fee');
    const next = withFlowView(chat, 'fee', { ...view, variables: [], nodes: [...view.nodes, { id: 'x', type: 'answer' }] });
    expect(next.variables).toEqual([]);
    expect(next.flows[1]!.nodes.map(n => n.id)).toEqual(['fee_start', 'x']);
    expect(next.flows[0]).toBe(chat.flows[0]);
    expect(JSON.stringify(next)).not.toContain('takenNodeIds');
  });

  it('generates node ids unique across flows', () => {
    expect(generateNodeId(flowView(chat, 'fee'), 'go')).toBe('go_1');
  });

  it('adds a flow with its own start node', () => {
    const next = addFlow(chat, { id: 'job', title: 'Việc làm', description: 'việc làm' });
    expect(next.flows[2]).toMatchObject({ id: 'job', entry: 'job_start', nodes: [{ id: 'job_start', type: 'start' }] });
    expect(addFlow(next, { id: 'job_2', title: 'x' }).flows[3]!.entry).toBe('job_2_start');
  });

  it('renames a flow everywhere it is named', () => {
    const next = updateFlow(chat, 'fee', { id: 'hoc_phi' });
    expect(next.flows[1]!.id).toBe('hoc_phi');
    expect(next.flows[0]!.nodes[1]!.config).toEqual({ flow: 'hoc_phi' });
    expect(updateFlow(chat, 'main', { id: 'chinh' }).router.default_flow).toBe('chinh');
    expect(updateFlow(chat, 'fee', { title: 'Phí', examples: ['phí'] }).flows[1]).toMatchObject({ title: 'Phí', examples: ['phí'] });
  });

  it('blocks removing the default flow or a goto target', () => {
    expect(flowRemovalBlockers(chat, 'main')).toEqual(['Đây là nghiệp vụ mặc định.']);
    expect(flowRemovalBlockers(chat, 'fee')).toEqual(['Node go (Chính) chuyển tới nghiệp vụ này.']);
    const extra = addFlow(chat, { id: 'job', title: 'Việc làm' });
    expect(flowRemovalBlockers(extra, 'job')).toEqual([]);
    expect(removeFlow(extra, 'job').flows.map(f => f.id)).toEqual(['main', 'fee']);
  });

  it('moves flows, sets the default and the router', () => {
    expect(moveFlow(chat, 'fee', -1).flows.map(f => f.id)).toEqual(['fee', 'main']);
    expect(moveFlow(chat, 'main', -1)).toBe(chat);
    expect(setDefaultFlow(chat, 'fee').router.default_flow).toBe('fee');
    expect(updateRouter(chat, { history_messages: 2 }).router).toEqual({ default_flow: 'main', history_messages: 2 });
  });

  it('lists node ids, the flow of a node and goto links', () => {
    expect(allNodeIds(chat)).toEqual(['start', 'go', 'fee_start']);
    expect(flowOfNode(chat, 'fee_start')).toBe('fee');
    expect(flowOfNode(chat, 'nope')).toBeUndefined();
    expect(gotoLinks(chat)).toEqual([{ from: 'main', to: 'fee', nodeId: 'go' }]);
  });

  it('renames and protects a variable that only a flow trigger reads', () => {
    const triggered: Chatflow = {
      ...chat,
      flows: chat.flows.map(flow => (flow.id === 'fee' ? { ...flow, trigger: { '==': [{ var: 'conv.stage' }, 'fee'] } } : flow)),
    };
    const view = allFlowsView(triggered);
    expect(triggerUsage(view, 'stage')).toEqual(['Học phí']);
    expect(() => removeVariable(view, 'stage')).toThrow(/điều kiện kích hoạt/);
    const renamed = renameVariable({ mode: 'chatflow', workflow: triggered } as never, 'stage', 'journey').workflow as Chatflow;
    expect(renamed.flows[1]!.trigger).toEqual({ '==': [{ var: 'conv.journey' }, 'fee'] });
    expect(renamed.flows[0]!.trigger).toBeUndefined();
  });
});
