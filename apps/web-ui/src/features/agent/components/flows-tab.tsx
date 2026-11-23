'use client';

import { ArrowDown, ArrowUp, Pencil, Plus, Shuffle, Star, Trash2, Workflow } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { ConfirmDialog } from '@/features/knowledge';
import { conditionLines } from '../model/workflow/condition';
import {
  MAX_FLOWS, addFlow, allFlowsView, findFlow, flowRemovalBlockers, gotoLinks, moveFlow, removeFlow, setDefaultFlow,
  updateFlow, updateRouter,
} from '../model/workflow/flows';
import { parseChatflowIssuePath } from '../model/workflow/issue-path';
import { readableVariables } from '../model/workflow/variables';
import type { AgentIssue, Chatflow, ChatflowFlow, NodeTypeCatalog } from '../types';
import { FlowForm, type FlowFormValue } from './flow-form';
import { FlowMap } from './flow-map';
import { RouteTester } from './route-tester';

type Editing = { flowId: string | null } | null;

/** Issues that belong to one flow: its profile fields and every node or edge inside it. */
function issueCount(issues: AgentIssue[], chat: Chatflow, flowId: string): number {
  return issues.filter(issue => {
    const target = parseChatflowIssuePath(issue.path, chat);
    return (target.kind === 'flow' && target.flowId === flowId)
      || ((target.kind === 'node' || target.kind === 'edge') && target.flowId === flowId);
  }).length;
}

/**
 * The Nghiệp vụ tab: every flow of the chatflow with what routes a turn into it, the router's own settings, a map of
 * the routes and a routing test. Graphs are edited on the Sơ đồ tab; this tab edits what sits above them.
 */
export function FlowsTab({ chat, catalog, issues, readOnly = false, onChange, onOpenFlow, beforeRun }: {
  chat: Chatflow;
  catalog?: NodeTypeCatalog;
  issues: AgentIssue[];
  readOnly?: boolean;
  onChange: (next: Chatflow) => void;
  /** Opens a flow's graph on the Sơ đồ tab. */
  onOpenFlow: (flowId: string) => void;
  beforeRun?: () => Promise<boolean>;
}) {
  const [editing, setEditing] = useState<Editing>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const [routed, setRouted] = useState<string | null>(null);
  // A trigger runs before any node: it reads sys, conv, profile and result, never a node's output.
  const triggerVariables = useMemo(() => readableVariables(allFlowsView(chat), catalog, '')
    .map(group => ({ ...group, items: group.items.filter(item => /^(sys|conv|profile|result)\./.test(item.path)) }))
    .filter(group => group.items.length > 0), [chat, catalog]);
  const gotos = gotoLinks(chat);
  const editingFlow = editing?.flowId ? findFlow(chat, editing.flowId) : undefined;
  const removingFlow = removing ? findFlow(chat, removing) : undefined;

  const save = (value: FlowFormValue) => {
    const profile = { title: value.title, description: value.description, examples: value.examples,
      trigger: value.trigger, routable: value.routable };
    let next = editingFlow
      ? updateFlow(chat, editingFlow.id, { id: value.id, ...profile })
      : updateFlow(addFlow(chat, { id: value.id, title: value.title }), value.id, profile);
    if (value.isDefault) next = setDefaultFlow(next, value.id);
    onChange(next);
    setEditing(null);
  };

  return (
    <section aria-label="Nghiệp vụ" className="mx-auto grid h-full max-w-6xl gap-4 overflow-y-auto lg:grid-cols-[minmax(0,1fr)_minmax(0,28rem)]">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold">Nghiệp vụ <span className="font-normal text-muted-foreground">({chat.flows.length}/{MAX_FLOWS})</span></h3>
            <p className="text-xs text-muted-foreground">
              Mỗi lượt chat, router chọn một nghiệp vụ: điều kiện kích hoạt trước (theo thứ tự dưới đây), rồi theo mô tả và câu mẫu, không khớp thì dùng nghiệp vụ mặc định.
            </p>
          </div>
          {!readOnly ? (
            <Button size="sm" disabled={chat.flows.length >= MAX_FLOWS} onClick={() => setEditing({ flowId: null })}
              title={chat.flows.length >= MAX_FLOWS ? `Tối đa ${MAX_FLOWS} nghiệp vụ` : undefined}>
              <Plus className="mr-1 size-4" aria-hidden /> Thêm nghiệp vụ
            </Button>
          ) : null}
        </div>

        <ol className="space-y-2">
          {chat.flows.map((flow, index) => (
            <FlowCard
              key={flow.id}
              chat={chat}
              flow={flow}
              index={index}
              readOnly={readOnly}
              highlighted={routed === flow.id}
              issues={issueCount(issues, chat, flow.id)}
              gotoTargets={gotos.filter(link => link.from === flow.id).map(link => findFlow(chat, link.to)?.title ?? link.to)}
              onEdit={() => setEditing({ flowId: flow.id })}
              onOpen={() => onOpenFlow(flow.id)}
              onMove={delta => onChange(moveFlow(chat, flow.id, delta))}
              onRemove={() => setRemoving(flow.id)}
            />
          ))}
        </ol>
      </div>

      <div className="space-y-3">
        <RouteTester chat={chat} beforeRun={beforeRun} onRouted={setRouted} />
        <FlowMap chat={chat} highlight={routed} />
        <RouterSettings chat={chat} readOnly={readOnly} onChange={onChange} />
      </div>

      <Dialog open={editing !== null} onOpenChange={open => { if (!open) setEditing(null); }}>
        <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
          <DialogTitle>{editingFlow ? `Sửa nghiệp vụ ${editingFlow.title}` : 'Thêm nghiệp vụ'}</DialogTitle>
          <DialogDescription className="text-sm text-muted-foreground">
            Mô tả và câu mẫu là những gì router đọc để chọn nghiệp vụ; các bước xử lý sửa ở tab Sơ đồ.
          </DialogDescription>
          {editing ? (
            <FlowForm key={editing.flowId ?? 'new'} chat={chat} flow={editingFlow} variables={triggerVariables}
              onSave={save} onCancel={() => setEditing(null)} />
          ) : null}
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={removing !== null}
        onOpenChange={open => { if (!open) setRemoving(null); }}
        title={`Xoá nghiệp vụ ${removingFlow?.title ?? ''}?`}
        description={`Xoá cả ${removingFlow?.nodes.length ?? 0} node của nghiệp vụ này. Biến hội thoại dùng chung vẫn giữ nguyên.`}
        confirmLabel="Xoá nghiệp vụ"
        destructive
        onConfirm={() => { if (removing) onChange(removeFlow(chat, removing)); setRemoving(null); }}
      />
    </section>
  );
}

function FlowCard({ chat, flow, index, readOnly, highlighted, issues, gotoTargets, onEdit, onOpen, onMove, onRemove }: {
  chat: Chatflow;
  flow: ChatflowFlow;
  index: number;
  readOnly: boolean;
  highlighted: boolean;
  issues: number;
  gotoTargets: string[];
  onEdit: () => void;
  onOpen: () => void;
  onMove: (delta: -1 | 1) => void;
  onRemove: () => void;
}) {
  const isDefault = chat.router.default_flow === flow.id;
  const blockers = flowRemovalBlockers(chat, flow.id);
  const trigger = flow.trigger ? conditionLines(flow.trigger, 2) : [];
  const examples = flow.examples ?? [];
  const iconButton = 'rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-30';
  return (
    <li data-testid={`flow-card-${flow.id}`}
      className={`rounded-lg border bg-card p-3 transition-colors ${highlighted ? 'border-primary ring-2 ring-primary/20' : ''}`}>
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md bg-muted font-mono text-xs">{index + 1}</span>
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <h4 className="truncate text-sm font-semibold">{flow.title}</h4>
            <code className="text-xs text-muted-foreground">{flow.id}</code>
            {isDefault ? (
              <span className="inline-flex items-center gap-1 rounded bg-amber-100 px-1.5 py-0.5 text-[11px] font-medium text-amber-900 dark:bg-amber-500/20 dark:text-amber-200">
                <Star aria-hidden className="size-3 fill-current" /> Mặc định
              </span>
            ) : null}
            {flow.routable === false ? <span className="rounded bg-muted px-1.5 py-0.5 text-[11px]">Không qua router</span> : null}
            {issues ? <span className="rounded bg-destructive/10 px-1.5 py-0.5 text-[11px] text-destructive">{issues} lỗi</span> : null}
          </div>
          <p className="line-clamp-2 text-xs text-muted-foreground">{flow.description?.trim() || 'Chưa có mô tả.'}</p>
          <div className="flex flex-wrap gap-1.5 text-[11px]">
            <span className="rounded bg-muted px-1.5 py-0.5">{examples.length} câu mẫu</span>
            <span className="rounded bg-muted px-1.5 py-0.5">{flow.nodes.length} node</span>
            {trigger.length ? (
              <span className="rounded bg-amber-50 px-1.5 py-0.5 font-mono text-amber-900 dark:bg-amber-500/10 dark:text-amber-200">
                Kích hoạt khi: {trigger.join(' ')}
              </span>
            ) : null}
            {gotoTargets.map(title => (
              <span key={title} className="inline-flex items-center gap-1 rounded bg-cyan-50 px-1.5 py-0.5 text-cyan-900 dark:bg-cyan-500/10 dark:text-cyan-200">
                <Shuffle aria-hidden className="size-3" /> {title}
              </span>
            ))}
          </div>
        </div>
        <div className="flex shrink-0 items-center">
          <button type="button" className={iconButton} aria-label={`Mở sơ đồ ${flow.title}`} title="Mở sơ đồ" onClick={onOpen}>
            <Workflow className="size-4" />
          </button>
          {!readOnly ? (
            <>
              <button type="button" className={iconButton} aria-label={`Sửa ${flow.title}`} title="Sửa" onClick={onEdit}>
                <Pencil className="size-4" />
              </button>
              <button type="button" className={iconButton} aria-label={`Đưa ${flow.title} lên`} title="Lên (xét kích hoạt trước)"
                disabled={index === 0} onClick={() => onMove(-1)}>
                <ArrowUp className="size-4" />
              </button>
              <button type="button" className={iconButton} aria-label={`Đưa ${flow.title} xuống`} title="Xuống"
                disabled={index === chat.flows.length - 1} onClick={() => onMove(1)}>
                <ArrowDown className="size-4" />
              </button>
              <button type="button" className={`${iconButton} hover:bg-destructive/10 hover:text-destructive`} aria-label={`Xoá ${flow.title}`}
                title={blockers.length ? blockers.join(' ') : 'Xoá'} disabled={blockers.length > 0 || chat.flows.length === 1} onClick={onRemove}>
                <Trash2 className="size-4" />
              </button>
            </>
          ) : null}
        </div>
      </div>
    </li>
  );
}

/** The router's own settings: which model classifies, how much history it sees, and extra guidance. */
function RouterSettings({ chat, readOnly, onChange }: { chat: Chatflow; readOnly: boolean; onChange: (next: Chatflow) => void }) {
  const router = chat.router;
  const routable = chat.flows.filter(flow => flow.routable !== false).length;
  return (
    <section aria-label="Cài đặt router" className="space-y-3 rounded-lg border bg-card p-3">
      <div>
        <h4 className="text-sm font-semibold">Router</h4>
        <p className="text-xs text-muted-foreground">
          {routable >= 2 ? `Gọi LLM một lần mỗi lượt để chọn giữa ${routable} nghiệp vụ.` : 'Chỉ có một nghiệp vụ định tuyến được: router không gọi LLM.'}
        </p>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="router-default">Nghiệp vụ mặc định</Label>
        <select id="router-default" disabled={readOnly} value={router.default_flow}
          onChange={event => onChange(setDefaultFlow(chat, event.target.value))}
          className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm disabled:opacity-50">
          {chat.flows.filter(flow => flow.routable !== false).map(flow => <option key={flow.id} value={flow.id}>{flow.title}</option>)}
        </select>
      </div>
      <div className="grid grid-cols-[1fr_7rem] gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="router-model">Model</Label>
          <Input id="router-model" disabled={readOnly} value={router.model ?? ''} placeholder="Model của agent"
            onChange={event => onChange(updateRouter(chat, { model: event.target.value.trim() ? event.target.value : null }))} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="router-history">Tin nhắn trước</Label>
          <Input id="router-history" type="number" min={0} max={6} disabled={readOnly} value={router.history_messages ?? 0}
            onChange={event => onChange(updateRouter(chat, { history_messages: Math.max(0, Math.min(6, Number(event.target.value) || 0)) }))} />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="router-instructions">Hướng dẫn thêm</Label>
        <Textarea id="router-instructions" rows={3} maxLength={2000} disabled={readOnly} value={router.instructions ?? ''}
          placeholder="Ví dụ: câu hỏi về điểm chuẩn thuộc Tuyển sinh, không thuộc Học phí."
          onChange={event => onChange(updateRouter(chat, { instructions: event.target.value }))} />
      </div>
    </section>
  );
}
