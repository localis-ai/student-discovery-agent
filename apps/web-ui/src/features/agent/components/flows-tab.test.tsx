import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { useState } from 'react';
import { streamDebugRun, type DebugRunEvent } from '../api/debug-run';
import type { Chatflow, NodeTypeCatalog, WorkflowDebugRunResult } from '../types';
import { FlowsTab } from './flows-tab';

vi.mock('../api/debug-run', () => ({ streamDebugRun: vi.fn() }));

const CHAT: Chatflow = {
  variables: [{ name: 'stage', type: 'enum', values: ['a', 'b'], default: 'a' }],
  router: { default_flow: 'main' },
  flows: [
    {
      id: 'main', title: 'Hỏi đáp chung', description: 'Mọi câu hỏi khác', examples: ['chào bạn'], entry: 'start',
      nodes: [{ id: 'start', type: 'start' }, { id: 'go', type: 'goto_flow', config: { flow: 'fee' } }], edges: [],
    },
    {
      id: 'fee', title: 'Học phí', description: 'Học sinh hỏi học phí', entry: 'fee_start',
      trigger: { '==': [{ var: 'sys.interaction_outcome' }, 'assessment_completed'] },
      nodes: [{ id: 'fee_start', type: 'start' }], edges: [],
    },
  ],
};

const catalog = {
  catalog_version: 'v',
  node_types: [],
  namespaces: [
    { name: 'sys', title: 'Hệ thống', access: 'read_only', source: 'static', variables: [{ name: 'interaction_outcome', type: 'string', values: ['none', 'assessment_completed'] }] },
    { name: 'conv', title: 'Biến hội thoại', access: 'assign_only', source: 'workflow_variables' },
  ],
} as unknown as NodeTypeCatalog;

function Harness({ onChange = () => {}, onOpenFlow = () => {}, initial = CHAT }: {
  onChange?: (next: Chatflow) => void; onOpenFlow?: (id: string) => void; initial?: Chatflow;
}) {
  const [chat, setChat] = useState(initial);
  return (
    <FlowsTab chat={chat} catalog={catalog} issues={[{ path: 'workflow.flows[1].nodes[0]', code: 'x', message: 'lỗi' }]}
      onOpenFlow={onOpenFlow} onChange={next => { setChat(next); onChange(next); }} />
  );
}

afterEach(() => cleanup());

describe('FlowsTab', () => {
  it('lists each flow with its default mark, trigger, examples, goto targets and issues', () => {
    render(<Harness />);
    const main = screen.getByTestId('flow-card-main');
    expect(main).toHaveTextContent('Hỏi đáp chung');
    expect(main).toHaveTextContent('Mặc định');
    expect(main).toHaveTextContent('1 câu mẫu');
    expect(main).toHaveTextContent('Học phí'); // goto chip
    const fee = screen.getByTestId('flow-card-fee');
    expect(fee).toHaveTextContent('Kích hoạt khi:');
    expect(fee).toHaveTextContent('assessment_completed');
    expect(fee).toHaveTextContent('1 lỗi');
    expect(screen.getByText('(2/10)')).toBeInTheDocument();
  });

  it('adds a flow with its own start node from the dialog', () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: 'Thêm nghiệp vụ' }));
    const dialog = screen.getByRole('dialog', { name: 'Thêm nghiệp vụ' });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Thêm nghiệp vụ' }));
    expect(within(dialog).getByText('Cần tiêu đề.')).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.change(within(dialog).getByLabelText('Tiêu đề'), { target: { value: 'Việc làm' } });
    fireEvent.change(within(dialog).getByLabelText('Mã nghiệp vụ'), { target: { value: 'viec_lam' } });
    fireEvent.change(within(dialog).getByLabelText('Mô tả cho router'), { target: { value: 'Hỏi cơ hội việc làm' } });
    fireEvent.change(within(dialog).getByLabelText('Câu mẫu'), { target: { value: 'ra trường làm gì\n\nlương bao nhiêu' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Thêm nghiệp vụ' }));
    const next = onChange.mock.lastCall![0] as Chatflow;
    expect(next.flows[2]).toMatchObject({
      id: 'viec_lam', title: 'Việc làm', description: 'Hỏi cơ hội việc làm', examples: ['ra trường làm gì', 'lương bao nhiêu'],
      trigger: null, routable: true, entry: 'viec_lam_start', nodes: [{ id: 'viec_lam_start', type: 'start' }],
    });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('rejects a taken or reserved id', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: 'Thêm nghiệp vụ' }));
    const dialog = screen.getByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText('Tiêu đề'), { target: { value: 'X' } });
    fireEvent.change(within(dialog).getByLabelText('Mô tả cho router'), { target: { value: 'x' } });
    fireEvent.change(within(dialog).getByLabelText('Mã nghiệp vụ'), { target: { value: 'fee' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Thêm nghiệp vụ' }));
    expect(within(dialog).getByText('Id này đã có nghiệp vụ khác dùng.')).toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText('Mã nghiệp vụ'), { target: { value: 'other' } });
    expect(within(dialog).getByText('Không dùng other hoặc error.')).toBeInTheDocument();
  });

  it('renames a flow, carries the id to goto nodes and makes it the default', () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: 'Sửa Học phí' }));
    const dialog = screen.getByRole('dialog', { name: 'Sửa nghiệp vụ Học phí' });
    fireEvent.change(within(dialog).getByLabelText('Mã nghiệp vụ'), { target: { value: 'hoc_phi' } });
    fireEvent.click(within(dialog).getByLabelText('Nghiệp vụ mặc định'));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Lưu nghiệp vụ' }));
    const next = onChange.mock.lastCall![0] as Chatflow;
    expect(next.flows[1]!.id).toBe('hoc_phi');
    expect(next.flows[1]!.trigger).toEqual(CHAT.flows[1]!.trigger);
    expect(next.flows[0]!.nodes[1]!.config).toEqual({ flow: 'hoc_phi' });
    expect(next.router.default_flow).toBe('hoc_phi');
  });

  it('blocks removing the default flow or a goto target, and removes another after confirmation', async () => {
    const extra: Chatflow = { ...CHAT, flows: [...CHAT.flows, { id: 'job', title: 'Việc làm', description: 'x', entry: 'job_s', nodes: [{ id: 'job_s', type: 'start' }] }] };
    const onChange = vi.fn();
    render(<Harness initial={extra} onChange={onChange} />);
    expect(screen.getByRole('button', { name: 'Xoá Hỏi đáp chung' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Xoá Học phí' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Xoá Việc làm' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Xoá nghiệp vụ' }));
    await waitFor(() => expect((onChange.mock.lastCall![0] as Chatflow).flows.map(flow => flow.id)).toEqual(['main', 'fee']));
  });

  it('reorders flows and opens a flow graph', () => {
    const onChange = vi.fn();
    const onOpenFlow = vi.fn();
    render(<Harness onChange={onChange} onOpenFlow={onOpenFlow} />);
    expect(screen.getByRole('button', { name: 'Đưa Hỏi đáp chung lên' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Đưa Học phí lên' }));
    expect((onChange.mock.lastCall![0] as Chatflow).flows.map(flow => flow.id)).toEqual(['fee', 'main']);
    fireEvent.click(screen.getByRole('button', { name: 'Mở sơ đồ Học phí' }));
    expect(onOpenFlow).toHaveBeenCalledWith('fee');
  });

  it('edits the router settings', () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    const router = screen.getByRole('region', { name: 'Cài đặt router' });
    expect(router).toHaveTextContent('Gọi LLM một lần mỗi lượt để chọn giữa 2 nghiệp vụ.');
    fireEvent.change(within(router).getByLabelText('Tin nhắn trước'), { target: { value: '9' } });
    expect((onChange.mock.lastCall![0] as Chatflow).router.history_messages).toBe(6);
    fireEvent.change(within(router).getByLabelText('Hướng dẫn thêm'), { target: { value: 'Ưu tiên học phí' } });
    expect((onChange.mock.lastCall![0] as Chatflow).router.instructions).toBe('Ưu tiên học phí');
  });

  it('tests routing with a route-only run and highlights the picked flow', async () => {
    const result = {
      run_id: 'dbg_0123456789abcdef01234567', status: 'completed', path: ['router'], node_runs: [], blocks: [], effects: [],
      llm_calls: 1, live_llm_calls: 1, tokens: { input: 1, output: 1 }, created_at: '2026-11-23T00:00:00Z',
      expires_at: '2026-11-24T00:00:00Z', route: { flow: 'fee', method: 'classifier', label: 'fee' },
    } as WorkflowDebugRunResult;
    vi.mocked(streamDebugRun).mockImplementation(async function* () { yield { event: 'completed', result } as DebugRunEvent; });
    render(<Harness />);
    fireEvent.change(screen.getByLabelText('Câu thử định tuyến'), { target: { value: 'học phí bao nhiêu' } });
    fireEvent.click(screen.getByRole('button', { name: 'Thử' }));
    expect(await screen.findByRole('status')).toHaveTextContent('→ Học phí · phân loại theo mô tả');
    expect(vi.mocked(streamDebugRun).mock.lastCall![0]).toEqual({ message: 'học phí bao nhiêu', stop_after: 'route' });
    await waitFor(() => expect(screen.getByTestId('flow-card-fee').className).toContain('border-primary'));
    expect(screen.getByTestId('flow-map-fee').className).toContain('border-primary');
  });
});
