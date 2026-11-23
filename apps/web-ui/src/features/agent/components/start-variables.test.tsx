import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { useState } from 'react';
import type { AgentConfig, Chatflow, NodeTypeCatalog } from '../types';
import { flowView } from '../model/workflow/flows';
import { StartVariables } from './start-variables';
import { VariablesProvider } from './variables-provider';

const SEED: AgentConfig = {
  workflow: {
    variables: [
      { name: 'stage', type: 'enum', values: ['a', 'b'], default: 'a', description: 'Giai đoạn' },
      { name: 'free', type: 'string', default: '' },
    ],
    router: { default_flow: 'main' },
    flows: [
      {
        id: 'main', title: 'Chính', description: 'mọi thứ', entry: 'start',
        nodes: [
          { id: 'start', type: 'start' },
          { id: 'check', type: 'if_else', title: 'Kiểm tra', config: { condition: { '==': [{ var: 'conv.stage' }, 'b'] } } },
        ],
        edges: [],
      },
      {
        id: 'fee', title: 'Học phí', description: 'học phí', entry: 'fee_start',
        nodes: [
          { id: 'fee_start', type: 'start' },
          { id: 'fee_check', type: 'if_else', config: { condition: { '==': [{ var: 'conv.stage' }, 'a'] } } },
        ],
      },
    ],
  },
  persona_cases: [{ id: 'p', title: 'P', initial_state: { conv: { stage: 'a' } }, turns: [{ input: { text: 'x' } }] }],
};
const catalog = {
  catalog_version: 'v',
  node_types: [],
  namespaces: [
    { name: 'sys', title: 'Hệ thống', access: 'read_only', source: 'static', variables: [{ name: 'query', type: 'string', description: 'Câu học sinh vừa gõ' }] },
    { name: 'conv', title: 'Biến hội thoại', access: 'assign_only', source: 'workflow_variables' },
  ],
} as unknown as NodeTypeCatalog;

function Harness({ onConfig, readOnly = false }: { onConfig: (next: AgentConfig) => void; readOnly?: boolean }) {
  const [config, setConfig] = useState(SEED);
  return (
    <VariablesProvider config={config} catalog={catalog} readOnly={readOnly} onJumpToNode={() => {}}
      onConfigChange={(next) => { setConfig(next); onConfig(next); }}>
      <StartVariables workflow={flowView(config.workflow as Chatflow, 'main')} catalog={catalog} />
    </VariablesProvider>
  );
}

const names = (config: AgentConfig) => (config.workflow as Chatflow).variables!.map((variable) => variable.name);

describe('StartVariables', () => {
  it('lists conversation variables with description, type and usage, and system variables read-only', () => {
    render(<Harness onConfig={() => {}} />);
    const row = screen.getByTestId('variable-stage');
    expect(row).toHaveTextContent('stage');
    expect(row).toHaveTextContent('Giai đoạn');
    expect(row).toHaveTextContent('enum');
    expect(row).toHaveTextContent('dùng ở 2 node'); // both flows read it
    expect(screen.getByText('Dùng chung cho mọi nghiệp vụ.')).toBeInTheDocument();
    expect(screen.getByTestId('variable-free')).toHaveTextContent('Chưa có mô tả');
    const system = screen.getByRole('region', { name: 'Biến hệ thống' });
    expect(within(system).getByText('sys.query')).toBeInTheDocument();
    expect(within(system).queryByRole('button')).not.toBeInTheDocument();
  });

  it('adds a variable from a dialog', () => {
    const onConfig = vi.fn();
    render(<Harness onConfig={onConfig} />);
    fireEvent.click(screen.getByRole('button', { name: 'Thêm biến' }));
    const dialog = screen.getByRole('dialog', { name: 'Thêm biến hội thoại' });
    fireEvent.change(within(dialog).getByLabelText('Tên biến'), { target: { value: 'score' } });
    fireEvent.click(within(dialog).getByRole('radio', { name: 'number' }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Lưu biến' }));
    expect(names(onConfig.mock.lastCall![0])).toEqual(['stage', 'free', 'score']);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('blocks deleting a variable in use and deletes an unused one', () => {
    const onConfig = vi.fn();
    render(<Harness onConfig={onConfig} />);
    expect(screen.getByRole('button', { name: 'Xoá conv.stage' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Xoá conv.free' }));
    fireEvent.click(screen.getByRole('button', { name: 'Xoá biến' }));
    expect(names(onConfig.mock.lastCall![0])).toEqual(['stage']);
  });

  it('renames a used variable everywhere, persona cases included, after confirmation', () => {
    const onConfig = vi.fn();
    render(<Harness onConfig={onConfig} />);
    fireEvent.click(screen.getByRole('button', { name: 'Sửa conv.stage' }));
    const dialog = screen.getByRole('dialog', { name: 'Sửa biến conv.stage' });
    fireEvent.change(within(dialog).getByLabelText('Tên biến'), { target: { value: 'journey' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Lưu biến' }));
    expect(onConfig).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Đổi tên ở 2 node' }));
    const next = onConfig.mock.lastCall![0];
    expect(names(next)).toEqual(['journey', 'free']);
    expect((next.workflow as Chatflow).flows[0]!.nodes[1]!.config!.condition).toEqual({ '==': [{ var: 'conv.journey' }, 'b'] });
    expect((next.workflow as Chatflow).flows[1]!.nodes[1]!.config!.condition).toEqual({ '==': [{ var: 'conv.journey' }, 'a'] });
    expect(next.persona_cases[0].initial_state.conv).toEqual({ journey: 'a' });
  });

  it('only lists variables when read-only', () => {
    render(<Harness onConfig={() => {}} readOnly />);
    expect(screen.queryByRole('button', { name: 'Thêm biến' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sửa conv.stage' })).toBeDisabled();
  });
});
