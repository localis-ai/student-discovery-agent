import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import type { AgentConfig, NodeTypeCatalog } from '../types';
import { VariablesSheet } from './variables-sheet';

const config: AgentConfig = {
  workflow: {
    entry: 'start',
    variables: [
      { name: 'stage', type: 'enum', values: ['a', 'b'], default: 'a', description: 'Giai đoạn' },
      { name: 'free', type: 'string', default: '' },
    ],
    nodes: [
      { id: 'start', type: 'start' },
      { id: 'check', type: 'if_else', title: 'Kiểm tra', config: { condition: { '==': [{ var: 'conv.stage' }, 'b'] } } },
    ],
    edges: [],
  },
};
const catalog = {
  catalog_version: 'v',
  node_types: [],
  namespaces: [
    { name: 'sys', title: 'Hệ thống', access: 'read_only', source: 'static', variables: [{ name: 'query', type: 'string', description: 'Câu học sinh vừa gõ' }] },
    { name: 'conv', title: 'Biến hội thoại', access: 'assign_only', source: 'workflow_variables' },
  ],
} as unknown as NodeTypeCatalog;

function setup() {
  const onConfigChange = vi.fn();
  const onJumpToNode = vi.fn();
  render(<VariablesSheet open onOpenChange={() => {}} config={config} catalog={catalog} onConfigChange={onConfigChange} onJumpToNode={onJumpToNode} />);
  return { onConfigChange, onJumpToNode };
}

describe('VariablesSheet', () => {
  it('lists conversation variables with description, type and usage', () => {
    setup();
    const row = screen.getByTestId('variable-stage');
    expect(row).toHaveTextContent('conv.stage');
    expect(row).toHaveTextContent('enum');
    expect(row).toHaveTextContent('Giai đoạn');
    expect(row).toHaveTextContent('dùng ở 1 node');
    expect(screen.getByTestId('variable-free')).toHaveTextContent('Chưa có mô tả');
  });

  it('jumps to a node that uses the variable', () => {
    const { onJumpToNode } = setup();
    fireEvent.click(within(screen.getByTestId('variable-stage')).getByRole('button', { name: 'dùng ở 1 node' }));
    fireEvent.click(screen.getByRole('button', { name: 'Kiểm tra' }));
    expect(onJumpToNode).toHaveBeenCalledWith('check');
  });

  it('blocks deleting a variable in use and deletes an unused one', () => {
    const { onConfigChange } = setup();
    expect(within(screen.getByTestId('variable-stage')).getByRole('button', { name: 'Xoá conv.stage' })).toBeDisabled();
    fireEvent.click(within(screen.getByTestId('variable-free')).getByRole('button', { name: 'Xoá conv.free' }));
    fireEvent.click(screen.getByRole('button', { name: 'Xoá biến' }));
    expect(onConfigChange.mock.lastCall![0].workflow.variables.map((variable: { name: string }) => variable.name)).toEqual(['stage']);
  });

  it('adds a variable', () => {
    const { onConfigChange } = setup();
    fireEvent.click(screen.getByRole('button', { name: 'Thêm biến' }));
    fireEvent.change(screen.getByLabelText('Tên biến'), { target: { value: 'score' } });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu biến' }));
    expect(onConfigChange.mock.lastCall![0].workflow.variables.map((variable: { name: string }) => variable.name))
      .toEqual(['stage', 'free', 'score']);
  });

  it('renames a used variable everywhere after confirmation', () => {
    const { onConfigChange } = setup();
    fireEvent.click(within(screen.getByTestId('variable-stage')).getByRole('button', { name: 'Sửa conv.stage' }));
    fireEvent.change(screen.getByLabelText('Tên biến'), { target: { value: 'journey' } });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu biến' }));
    expect(onConfigChange).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Đổi tên ở 1 node' }));
    const next = onConfigChange.mock.lastCall![0];
    expect(next.workflow.nodes[1].config.condition).toEqual({ '==': [{ var: 'conv.journey' }, 'b'] });
    expect(next.workflow.variables.map((variable: { name: string }) => variable.name)).toEqual(['journey', 'free']);
  });

  it('shows system variables read-only', () => {
    setup();
    fireEvent.click(screen.getByRole('tab', { name: 'Biến hệ thống' }));
    expect(screen.getByText('sys.query')).toBeInTheDocument();
    expect(screen.getByText('Câu học sinh vừa gõ')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Sửa sys/ })).not.toBeInTheDocument();
  });
});
