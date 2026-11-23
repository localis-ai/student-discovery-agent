import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { agentApi } from '../api/agent';
import { setIn, type Path } from '../model/config';
import type { SectionId } from '../model/sections';
import type { AgentConfig, NodeTypeCatalog } from '../types';
import { ConfigTab } from './config-tab';
import type { ValidationState } from './issues-panel';

vi.mock('@/features/knowledge', async original => ({
  ...(await original<typeof import('@/features/knowledge')>()),
  useKnowledgeBases: () => ({ data: [{ id: 'kb1', name: 'KB 1' }] }),
}));

const nodeCatalog: NodeTypeCatalog = {
  catalog_version: 'test',
  namespaces: [],
  node_types: [
    { type: 'start', title: 'Bắt đầu', description: 'Entry', config_schema: {}, handles: { static: ['next'] }, output_schema: {} },
    {
      type: 'answer', title: 'Trả lời', description: 'Answer', handles: { static: [] }, output_schema: {},
      config_schema: { type: 'object', properties: { blocks: { type: 'array', default: [] } } },
    },
  ],
};
vi.mock('../api/agent', () => ({ agentApi: { getNodeTypes: vi.fn(async () => nodeCatalog) } }));

const SEED: AgentConfig = { greeting_text: 'Chào', persona: { name: 'IHRD', system_prompt: 'x' }, model: { ref: 'gemini/x' }, extra_field: { keep: true } };

function Harness({
  validation = null, onConfig = () => {}, initial = SEED, initialSection = 'persona' as SectionId, mode = 'agent' as 'agent' | 'chatflow',
  onJsonValidity = () => {},
}: {
  validation?: ValidationState | null; onConfig?: (c: AgentConfig) => void; initial?: AgentConfig; initialSection?: SectionId; mode?: 'agent' | 'chatflow';
  onJsonValidity?: (error: string | null) => void;
}) {
  const [config, setConfig] = useState(initial);
  const [section, setSection] = useState<SectionId>(initialSection);
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [chatflowOpen, setChatflowOpen] = useState(initialSection === 'chatflow');
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false } } }));
  const update = (next: AgentConfig) => { setConfig(next); onConfig(next); };
  return (
    <QueryClientProvider client={client}>
      <ConfigTab config={config} onChange={(path: Path, value) => update(setIn(config, path, value))} onReplace={update}
        section={section} onSection={id => { if (!jsonError) setSection(id); }} onJsonValidity={error => { setJsonError(error); onJsonValidity(error); }}
        validation={validation} onBindKb={() => {}} mode={mode} chatflowOpen={chatflowOpen} onChatflowOpen={setChatflowOpen} />
    </QueryClientProvider>
  );
}

/** A one-flow chatflow around a single graph, as the draft stores it. */
const one = (graph: Record<string, unknown>) => ({
  router: { default_flow: 'main' },
  flows: [{ id: 'main', title: 'Chính', description: 'Mọi câu hỏi', ...graph }],
});

const CHATFLOW_SEED: AgentConfig = {
  ...SEED, mode: 'chatflow', workflow: one({ entry: 'start', nodes: [{ id: 'start', type: 'start' }, { id: 'a', type: 'answer' }], edges: [] }),
};

describe('ConfigTab', () => {
  it('edits a form field and keeps fields the form does not show', () => {
    const onConfig = vi.fn();
    render(<Harness onConfig={onConfig} />);
    fireEvent.change(screen.getByLabelText('Tên agent'), { target: { value: 'Mentor' } });
    expect(onConfig).toHaveBeenLastCalledWith(expect.objectContaining({ persona: expect.objectContaining({ name: 'Mentor' }), extra_field: { keep: true } }));
  });

  it('shares state with the JSON tab and blocks leaving it while JSON is broken', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: 'JSON' }));
    const editor = screen.getByLabelText('Cấu hình JSON');
    expect((editor as HTMLTextAreaElement).value).toContain('"extra_field"');
    fireEvent.change(editor, { target: { value: '{ "greeting_text": ' } });
    expect(screen.getByRole('alert')).toHaveTextContent('JSON chưa hợp lệ');
    fireEvent.click(screen.getByRole('button', { name: 'Model' }));
    expect(screen.getByLabelText('Cấu hình JSON')).toBeInTheDocument();
  });

  it('jumps to the field of a clicked issue', async () => {
    const validation = { issues: [{ path: 'model.ref', code: 'value_error', message: 'Provider không hỗ trợ' }], valid: false, checkedAt: new Date().toISOString(), stale: false };
    render(<Harness validation={validation} />);
    fireEvent.click(screen.getByRole('button', { name: /Provider không hỗ trợ/ }));
    await new Promise(r => setTimeout(r, 0));
    expect(document.activeElement?.id).toBe('field-model.ref');
    expect(screen.getAllByText('Provider không hỗ trợ').length).toBeGreaterThan(1);
  });

  it('shares workflow state in the Chatflow JSON tab and blocks leaving while JSON is broken', () => {
    const onConfig = vi.fn();
    const chatflowSeed: AgentConfig = {
      ...SEED,
      mode: 'chatflow',
      workflow: one({ entry: 'start', nodes: [{ id: 'start', type: 'start', title: 'Bắt đầu' }], edges: [] }),
    };
    render(<Harness initial={chatflowSeed} initialSection="chatflow" mode="chatflow" onConfig={onConfig} />);

    fireEvent.click(screen.getByRole('tab', { name: 'JSON' }));
    const editor = screen.getByLabelText('Workflow JSON') as HTMLTextAreaElement;
    expect(editor.value).toContain('"entry": "start"');

    const edited = one({ entry: 'start', nodes: [{ id: 'start', type: 'start', title: 'Khởi đầu mới' }], edges: [] });
    fireEvent.change(editor, { target: { value: JSON.stringify(edited, null, 2) } });
    expect(onConfig).toHaveBeenLastCalledWith(expect.objectContaining({ workflow: edited, extra_field: { keep: true } }));

    fireEvent.change(editor, { target: { value: '{ "entry": ' } });
    expect(screen.getByRole('alert')).toHaveTextContent('JSON chưa hợp lệ');

    fireEvent.click(screen.getByRole('tab', { name: 'Sơ đồ' }));
    expect(screen.getByLabelText('Workflow JSON')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Model' }));
    expect(screen.getByLabelText('Workflow JSON')).toBeInTheDocument();
  });

  it('opens the flow of a clicked node issue on the canvas with that node selected', async () => {
    const chatflowSeed: AgentConfig = {
      ...SEED,
      mode: 'chatflow',
      workflow: {
        router: { default_flow: 'main' },
        flows: [
          { id: 'main', title: 'Chính', description: 'x', entry: 'start', nodes: [{ id: 'start', type: 'start' }], edges: [] },
          {
            id: 'fee', title: 'Học phí', description: 'y', entry: 'fee_start', edges: [],
            nodes: [
              { id: 'fee_start', type: 'start', title: 'Bắt đầu' },
              { id: 'classify', type: 'if_else', title: 'Phân nhánh', config: { labels: ['hoc_phi'] } },
            ],
          },
        ],
      },
    };
    const validation: ValidationState = {
      valid: false,
      stale: false,
      checkedAt: new Date().toISOString(),
      issues: [{ path: 'workflow.flows[1].nodes[1].config.labels[0]', code: 'workflow_unwired_label', message: 'Nhãn chưa nối' }],
    };
    render(<Harness initial={chatflowSeed} initialSection="model" mode="chatflow" validation={validation} />);

    expect(screen.queryByLabelText('Workflow JSON')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Nhãn chưa nối/ }));

    expect(await screen.findByRole('region', { name: /Biểu mẫu node Phân nhánh/ })).toBeInTheDocument();
    expect(screen.getByLabelText('Nghiệp vụ đang sửa')).toHaveValue('fee');
  });

  it('opens the Chatflow JSON tab and highlights the property of a router issue', async () => {
    const chatflowSeed: AgentConfig = { ...SEED, mode: 'chatflow', workflow: one({ entry: 'start', nodes: [{ id: 'start', type: 'start' }], edges: [] }) };
    const validation: ValidationState = {
      valid: false,
      stale: false,
      checkedAt: new Date().toISOString(),
      issues: [{ path: 'workflow.router.default_flow', code: 'workflow_flow_invalid', message: 'Mặc định sai' }],
    };
    render(<Harness initial={chatflowSeed} initialSection="model" mode="chatflow" validation={validation} />);
    fireEvent.click(screen.getByRole('button', { name: /Mặc định sai/ }));
    const editor = await screen.findByLabelText('Workflow JSON') as HTMLTextAreaElement;
    await new Promise(r => setTimeout(r, 0));
    expect(editor.value.slice(editor.selectionStart, editor.selectionEnd)).toContain('"default_flow"');
  });

  it('survives a half-typed workflow in the JSON tab and explains it on the canvas tab', () => {
    const chatflowSeed: AgentConfig = { ...SEED, mode: 'chatflow', workflow: one({ entry: 'start', nodes: [{ id: 'start', type: 'start' }], edges: [] }) };
    render(<Harness initial={chatflowSeed} initialSection="chatflow" mode="chatflow" />);
    fireEvent.click(screen.getByRole('tab', { name: 'JSON' }));
    // Valid JSON, wrong shape: one deleted letter of "flows".
    fireEvent.change(screen.getByLabelText('Workflow JSON'), { target: { value: '{ "router": { "default_flow": "main" }, "flow": [] }' } });
    fireEvent.click(screen.getByRole('tab', { name: 'Sơ đồ' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Chatflow chưa đúng cấu trúc');
    expect(screen.queryByTestId('workflow-canvas')).not.toBeInTheDocument();
  });

  it('does not carry a node form JSON field over to the next node, and blocks switching while it is broken', async () => {
    const onJsonValidity = vi.fn();
    const chatflowSeed: AgentConfig = {
      ...SEED,
      mode: 'chatflow',
      workflow: one({
        entry: 'start',
        nodes: [
          { id: 'start', type: 'start' },
          { id: 'a', type: 'answer', title: 'A' },
          { id: 'b', type: 'answer', title: 'B' },
        ],
        edges: [],
      }),
    };
    render(<Harness initial={chatflowSeed} initialSection="chatflow" mode="chatflow" onJsonValidity={onJsonValidity} />);
    await screen.findByTestId('workflow-node-palette');
    fireEvent.click(screen.getByTestId('workflow-node-a'));
    const blocks = await screen.findByLabelText('Block');
    fireEvent.change(blocks, { target: { value: '[ "half' } });
    expect(onJsonValidity).toHaveBeenLastCalledWith('Block: JSON chưa hợp lệ');

    fireEvent.click(screen.getByTestId('workflow-node-b'));
    expect(screen.getByRole('region', { name: /Biểu mẫu node A/ })).toBeInTheDocument();

    fireEvent.change(blocks, { target: { value: '[]' } });
    expect(onJsonValidity).toHaveBeenLastCalledWith(null);
    fireEvent.click(screen.getByTestId('workflow-node-b'));
    expect(screen.getByRole('region', { name: /Biểu mẫu node B/ })).toBeInTheDocument();
    expect(screen.getByLabelText('Block')).toHaveValue('[]');
  });

  it('opens the start node panel from the header Biến button and declares a variable in a dialog', async () => {
    const onConfig = vi.fn();
    render(<Harness initial={CHATFLOW_SEED} initialSection="chatflow" mode="chatflow" onConfig={onConfig} />);
    await screen.findByTestId('workflow-node-palette');
    fireEvent.click(screen.getByRole('button', { name: 'Biến (0)' }));
    const panel = screen.getByRole('complementary', { name: 'Cấu hình node' });
    expect(within(panel).getByRole('region', { name: 'Biến hội thoại' })).toBeInTheDocument();
    fireEvent.click(within(panel).getByRole('button', { name: 'Thêm biến' }));
    expect(screen.getByRole('dialog', { name: 'Thêm biến hội thoại' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Tên biến'), { target: { value: 'score' } });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu biến' }));
    expect(onConfig.mock.lastCall![0].workflow.variables).toEqual([{ name: 'score', type: 'string', default: '' }]);
    expect(onConfig.mock.lastCall![0].extra_field).toEqual({ keep: true });
  });

  it('opens the node panel over the canvas and closes it', async () => {
    render(<Harness initial={CHATFLOW_SEED} initialSection="chatflow" mode="chatflow" />);
    await screen.findByTestId('workflow-node-palette');
    fireEvent.click(screen.getByTestId('workflow-node-a'));
    const panel = screen.getByRole('complementary', { name: 'Cấu hình node' });
    expect(screen.getByTestId('workflow-canvas')).toContainElement(panel);
    fireEvent.click(screen.getByRole('button', { name: 'Đóng bảng node' }));
    expect(screen.queryByRole('complementary', { name: 'Cấu hình node' })).not.toBeInTheDocument();
  });

  it('shows a read-only preview and opens the full-window editor from it or from the section nav', async () => {
    function Closed() {
      const [open, setOpen] = useState(false);
      const [client] = useState(() => new QueryClient());
      return (
        <QueryClientProvider client={client}>
          <ConfigTab config={CHATFLOW_SEED} onChange={() => {}} onReplace={() => {}} section="chatflow" onSection={() => {}}
            onJsonValidity={() => {}} validation={null} onBindKb={() => {}} mode="chatflow" chatflowOpen={open} onChatflowOpen={setOpen} />
        </QueryClientProvider>
      );
    }
    render(<Closed />);
    expect(screen.getByTestId('workflow-canvas')).toBeInTheDocument();
    expect(screen.queryByTestId('workflow-node-palette')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Mở trình chỉnh sửa' }));
    const editor = screen.getByRole('dialog', { name: 'Trình chỉnh sửa Chatflow' });
    expect(editor).toContainElement(await screen.findByTestId('workflow-node-palette'));
    fireEvent.click(screen.getByRole('button', { name: /Về trang Agent/ }));
    expect(screen.queryByRole('dialog', { name: 'Trình chỉnh sửa Chatflow' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Chatflow' }));
    expect(screen.getByRole('dialog', { name: 'Trình chỉnh sửa Chatflow' })).toBeInTheDocument();
  });

  it('keeps the editor open while a JSON field is broken', () => {
    render(<Harness initial={CHATFLOW_SEED} initialSection="chatflow" mode="chatflow" />);
    fireEvent.click(screen.getByRole('tab', { name: 'JSON' }));
    fireEvent.change(screen.getByLabelText('Workflow JSON'), { target: { value: '{ "entry": ' } });
    expect(screen.getByRole('button', { name: /Về trang Agent/ })).toBeDisabled();
  });

  it('keeps the canvas read-only while the node catalog loads', () => {
    vi.mocked(agentApi.getNodeTypes).mockReturnValueOnce(new Promise(() => {}));
    render(<Harness initial={CHATFLOW_SEED} initialSection="chatflow" mode="chatflow" />);
    expect(screen.getByRole('status')).toHaveTextContent('Đang tải catalog node');
    expect(screen.getByTestId('workflow-canvas')).toBeInTheDocument();
    expect(screen.queryByTestId('workflow-node-palette')).not.toBeInTheDocument();
  });

  it('explains a failed catalog load and retries on request', async () => {
    vi.mocked(agentApi.getNodeTypes).mockRejectedValueOnce(new Error('runtime down'));
    render(<Harness initial={CHATFLOW_SEED} initialSection="chatflow" mode="chatflow" />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Không tải được catalog node');
    expect(screen.queryByTestId('workflow-node-palette')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
    expect(await screen.findByTestId('workflow-node-palette')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('resolves a stale report against the workflow it validated, not the edited one', () => {
    const edited: AgentConfig = {
      ...SEED,
      mode: 'chatflow',
      workflow: one({ entry: 'start', nodes: [{ id: 'start', type: 'start' }, { id: 'answer', type: 'answer' }], edges: [] }),
    };
    const validation: ValidationState = {
      valid: false,
      stale: true,
      checkedAt: new Date().toISOString(),
      issues: [{ path: 'workflow.flows[0].nodes[1].config.labels', code: 'workflow_unwired_label', message: 'Nhãn chưa nối' }],
      workflow: one({ entry: 'start', nodes: [{ id: 'start', type: 'start' }, { id: 'classify', type: 'if_else' }] }),
    };
    render(<Harness initial={edited} initialSection="chatflow" mode="chatflow" validation={validation} />);
    expect(screen.getByText('node classify')).toBeInTheDocument();
    expect(screen.queryByText('node answer')).not.toBeInTheDocument();
  });

  it('switches to the Chạy thử tab inside the Chatflow editor', () => {
    render(<Harness initial={CHATFLOW_SEED} initialSection="chatflow" mode="chatflow" />);
    expect(screen.getByLabelText('Chạy thử Chatflow')).not.toBeVisible();
    fireEvent.click(screen.getByRole('tab', { name: 'Chạy thử' }));
    expect(screen.getByLabelText('Chạy thử Chatflow')).toBeVisible();
  });

  it('keeps the debug tab mounted, with its input, across a switch to the canvas', () => {
    render(<Harness initial={CHATFLOW_SEED} initialSection="chatflow" mode="chatflow" />);
    fireEvent.click(screen.getByRole('tab', { name: 'Chạy thử' }));
    fireEvent.change(screen.getByLabelText('Nội dung input'), { target: { value: 'giữ nguyên' } });
    fireEvent.click(screen.getByRole('tab', { name: 'Sơ đồ' }));
    expect(screen.getByLabelText('Chạy thử Chatflow')).not.toBeVisible();
    fireEvent.click(screen.getByRole('tab', { name: 'Chạy thử' }));
    expect(screen.getByLabelText('Nội dung input')).toHaveValue('giữ nguyên');
  });
});

describe('ConfigTab with several flows', () => {
  const TWO: AgentConfig = {
    ...SEED,
    mode: 'chatflow',
    workflow: {
      variables: [],
      router: { default_flow: 'main' },
      flows: [
        { id: 'main', title: 'Chính', description: 'x', entry: 'start', nodes: [{ id: 'start', type: 'start' }, { id: 'a', type: 'answer', title: 'A' }], edges: [] },
        { id: 'fee', title: 'Học phí', description: 'y', entry: 'fee_start', nodes: [{ id: 'fee_start', type: 'start' }, { id: 'fee_a', type: 'answer', title: 'Phí' }], edges: [] },
      ],
    },
  };

  it('edits one flow at a time and writes back only that flow', async () => {
    const onConfig = vi.fn();
    render(<Harness initial={TWO} initialSection="chatflow" mode="chatflow" onConfig={onConfig} />);
    fireEvent.click(screen.getByRole('tab', { name: 'Sơ đồ' }));
    await screen.findByTestId('workflow-node-palette');
    expect(screen.getByTestId('workflow-node-a')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Nghiệp vụ đang sửa'), { target: { value: 'fee' } });
    expect(screen.queryByTestId('workflow-node-a')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('workflow-node-fee_a'));
    fireEvent.change(await screen.findByLabelText('Mô tả'), { target: { value: 'Trả lời học phí' } });
    const next = onConfig.mock.lastCall![0].workflow;
    expect(next.flows[1].nodes[1].description).toBe('Trả lời học phí');
    expect(next.flows[0]).toEqual((TWO.workflow as { flows: unknown[] }).flows[0]);
  });

  it('opens on the Nghiệp vụ tab and goes to a flow graph from its card', async () => {
    render(<Harness initial={TWO} initialSection="chatflow" mode="chatflow" />);
    expect(screen.getByRole('tab', { name: 'Nghiệp vụ' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByTestId('flow-card-fee')).toHaveTextContent('Học phí');
    fireEvent.click(screen.getByRole('button', { name: 'Mở sơ đồ Học phí' }));
    expect(screen.getByRole('tab', { name: 'Sơ đồ' })).toHaveAttribute('aria-selected', 'true');
    expect(await screen.findByTestId('workflow-node-fee_a')).toBeInTheDocument();
    expect(screen.getByLabelText('Nghiệp vụ đang sửa')).toHaveValue('fee');
  });
});
