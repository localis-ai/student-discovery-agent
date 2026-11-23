import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import type { ChatflowWorkflow, NodeTypeCatalog } from '../types';
import { NodeIoSection } from './node-io-section';
import { VariablesPanelContext, type VariablesPanel } from './variables-context';

const catalog = {
  catalog_version: 't',
  namespaces: [
    { name: 'sys', title: 'Hệ thống', access: 'read_only', source: 'static', variables: [{ name: 'query', type: 'string' }] },
    { name: 'conv', title: 'Biến hội thoại', access: 'assign_only', source: 'workflow_variables' },
  ],
  node_types: [
    { type: 'start', title: 'Bắt đầu', description: '', config_schema: {}, handles: { static: ['next'] }, output_schema: {} },
    { type: 'intent_classifier', title: 'Phân loại ý định', description: '', config_schema: {}, handles: { static: ['other'] }, output_schema: { properties: { label: { type: 'string' } } } },
    { type: 'llm', title: 'Gọi LLM', description: '', config_schema: {}, handles: { static: ['success'] }, output_schema: { properties: { text: { type: 'string' } } } },
  ],
} as unknown as NodeTypeCatalog;
const workflow: ChatflowWorkflow = {
  entry: 'start',
  variables: [{ name: 'stage', type: 'enum', values: ['a'], default: 'a' }],
  nodes: [
    { id: 'start', type: 'start', title: 'Bắt đầu lượt chat' },
    { id: 'classify', type: 'intent_classifier', title: 'Hiểu ý' },
    { id: 'gen', type: 'llm', title: 'Soạn', config: { prompt: '{{sys.query}} {{classify.label}} {{conv.stage}}' } },
  ],
  edges: [],
};

function renderWith(panel: Partial<VariablesPanel> = {}) {
  const value: VariablesPanel = { workflow, catalog, readOnly: false, edit: vi.fn(), remove: vi.fn(), jumpToNode: vi.fn(), ...panel };
  render(
    <VariablesPanelContext.Provider value={value}>
      <NodeIoSection node={workflow.nodes[2]!} workflow={workflow} catalog={catalog} />
    </VariablesPanelContext.Provider>,
  );
  return value;
}

describe('NodeIoSection', () => {
  it('lists inputs with their source and the outputs later nodes can read', () => {
    renderWith();
    const inputs = screen.getByRole('region', { name: 'Biến đầu vào' });
    expect(inputs).toHaveTextContent('sys.query');
    expect(inputs).toHaveTextContent('Hệ thống');
    expect(inputs).toHaveTextContent('Hiểu ý');
    expect(inputs).toHaveTextContent('Bắt đầu lượt chat');
    expect(screen.getByRole('region', { name: 'Biến đầu ra' })).toHaveTextContent('gen.text');
  });

  it('opens a conv variable and jumps to the node that produces an output', () => {
    const panel = renderWith();
    const inputs = screen.getByRole('region', { name: 'Biến đầu vào' });
    fireEvent.click(within(inputs).getByRole('button', { name: 'Sửa conv.stage' }));
    expect(panel.edit).toHaveBeenCalledWith('stage');
    fireEvent.click(within(inputs).getByRole('button', { name: 'Tới node Hiểu ý' }));
    expect(panel.jumpToNode).toHaveBeenCalledWith('classify');
    expect(within(inputs).queryByRole('button', { name: /sys\.query/ })).not.toBeInTheDocument();
  });
});
