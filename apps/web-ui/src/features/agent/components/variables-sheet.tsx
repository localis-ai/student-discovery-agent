'use client';

import { Pencil, Plus, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Input } from '@/components/ui/input';
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet';
import { ConfirmDialog } from '@/features/knowledge';
import { cn } from '@/lib/utils/cn';
import { removeVariable, renameVariable, upsertVariable, variableUsage } from '../model/workflow/variable-usage';
import type { AgentConfig, ChatflowVariable, ChatflowWorkflow, NodeTypeCatalog } from '../types';
import { VariableForm } from './variable-form';

const MAX_VARIABLES = 30;

type Editing = { mode: 'new' } | { mode: 'edit'; name: string } | null;
type PendingRename = { from: ChatflowVariable; to: ChatflowVariable; used: string[] } | null;

function constraintText(variable: ChatflowVariable): string {
  const limits = variable.constraints ?? {};
  const parts: string[] = [];
  if (variable.type === 'enum') parts.push(`${variable.values?.length ?? 0} giá trị`);
  if (limits.minimum !== undefined || limits.maximum !== undefined) parts.push(`${limits.minimum ?? '−∞'} – ${limits.maximum ?? '+∞'}`);
  if (limits.integer) parts.push('số nguyên');
  if (limits.min_length !== undefined || limits.max_length !== undefined) {
    parts.push(`${limits.min_length ?? 0}–${limits.max_length ?? '∞'} ký tự`);
  }
  if (limits.max_items !== undefined) parts.push(`≤ ${limits.max_items} phần tử`);
  if (limits.item_max_length !== undefined) parts.push(`mỗi phần tử ≤ ${limits.item_max_length} ký tự`);
  return parts.join(', ');
}

/** The Biến sheet: declare, edit, rename and remove conv.* variables; browse the read-only system variables. */
export function VariablesSheet({ open, onOpenChange, config, catalog, onConfigChange, onJumpToNode, createRequest }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  config: AgentConfig;
  catalog?: NodeTypeCatalog;
  onConfigChange: (next: AgentConfig) => void;
  onJumpToNode: (nodeId: string) => void;
  /** Set when a node form asked to declare a new variable: the sheet opens on a new form and reports the name. */
  createRequest?: { onCreated: (name: string) => void } | null;
}) {
  const workflow = config.workflow as ChatflowWorkflow;
  const variables = workflow.variables ?? [];
  const [tab, setTab] = useState<'conv' | 'system'>('conv');
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<Editing>(null);
  const [usageOpen, setUsageOpen] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [pendingRename, setPendingRename] = useState<PendingRename>(null);
  useEffect(() => {
    if (open && createRequest) {
      setTab('conv');
      setEditing({ mode: 'new' });
    }
  }, [open, createRequest]);

  const needle = search.trim().toLowerCase();
  const shown = variables.filter((variable) => !needle || `conv.${variable.name} ${variable.description ?? ''}`.toLowerCase().includes(needle));
  const titleOf = (id: string) => workflow.nodes.find((node) => node.id === id)?.title?.trim() || id;

  const finishSave = (variable: ChatflowVariable, previous?: ChatflowVariable) => {
    let next = config;
    if (previous && previous.name !== variable.name) next = renameVariable(next, previous.name, variable.name);
    const updated = upsertVariable(next.workflow as ChatflowWorkflow, variable, previous ? variable.name : undefined);
    onConfigChange({ ...next, workflow: updated });
    if (!previous) createRequest?.onCreated(variable.name);
    setEditing(null);
  };
  const save = (variable: ChatflowVariable) => {
    const previous = editing?.mode === 'edit' ? variables.find((item) => item.name === editing.name) : undefined;
    if (previous && previous.name !== variable.name) {
      const used = variableUsage(workflow, previous.name);
      if (used.length) {
        setPendingRename({ from: previous, to: variable, used });
        return;
      }
    }
    finishSave(variable, previous);
  };

  const systemSpaces = (catalog?.namespaces ?? []).filter((space) => space.name !== 'conv');
  const tabClass = (active: boolean) => (active
    ? 'flex-1 rounded-md bg-background px-3 py-1 font-medium shadow-sm'
    : 'flex-1 rounded-md px-3 py-1 text-muted-foreground hover:text-foreground');

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-[min(480px,100vw)] overflow-y-auto sm:max-w-none">
        <div>
          <SheetTitle>Biến</SheetTitle>
          <SheetDescription className="text-sm text-muted-foreground">Khai báo biến hội thoại mà các node đọc và ghi.</SheetDescription>
        </div>
        <div role="tablist" aria-label="Loại biến" className="flex gap-1 rounded-lg bg-muted p-0.5 text-sm">
          <button type="button" role="tab" aria-selected={tab === 'conv'} className={tabClass(tab === 'conv')} onClick={() => setTab('conv')}>
            Biến hội thoại
          </button>
          <button type="button" role="tab" aria-selected={tab === 'system'} className={tabClass(tab === 'system')} onClick={() => setTab('system')}>
            Biến hệ thống
          </button>
        </div>

        {tab === 'conv' ? (
          <div className="space-y-3">
            <div className="flex gap-2">
              <Input aria-label="Tìm biến" placeholder="Tìm biến…" className="h-8" value={search} onChange={(event) => setSearch(event.target.value)} />
              <button
                type="button"
                disabled={variables.length >= MAX_VARIABLES || editing !== null}
                className="inline-flex shrink-0 items-center gap-1 rounded-md border px-2.5 text-sm hover:bg-muted disabled:opacity-50"
                onClick={() => setEditing({ mode: 'new' })}
              >
                <Plus className="size-4" aria-hidden /> Thêm biến
              </button>
            </div>
            {editing?.mode === 'new' ? (
              <VariableForm others={variables} onSave={save} onCancel={() => setEditing(null)} />
            ) : null}
            <ul className="divide-y rounded-lg border">
              {shown.map((variable) => {
                if (editing?.mode === 'edit' && editing.name === variable.name) {
                  return (
                    <li key={variable.name} className="p-2">
                      <VariableForm initial={variable} others={variables} onSave={save} onCancel={() => setEditing(null)} />
                    </li>
                  );
                }
                const used = variableUsage(workflow, variable.name);
                const limits = constraintText(variable);
                return (
                  <li key={variable.name} data-testid={`variable-${variable.name}`} className="space-y-1 px-3 py-2.5">
                    <div className="flex items-center gap-2">
                      <code className="min-w-0 flex-1 truncate text-sm font-medium">conv.{variable.name}</code>
                      <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground">{variable.type}</span>
                      <button
                        type="button"
                        aria-label={`Sửa conv.${variable.name}`}
                        disabled={editing !== null}
                        className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-40"
                        onClick={() => setEditing({ mode: 'edit', name: variable.name })}
                      >
                        <Pencil className="size-3.5" />
                      </button>
                      <button
                        type="button"
                        aria-label={`Xoá conv.${variable.name}`}
                        disabled={used.length > 0}
                        title={used.length ? `Đang dùng ở ${used.length} node, không xoá được` : undefined}
                        className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive disabled:pointer-events-none disabled:opacity-40"
                        onClick={() => setPendingDelete(variable.name)}
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </div>
                    <p className={cn('text-sm', variable.description ? 'text-foreground/80' : 'text-muted-foreground')}>
                      {variable.description || 'Chưa có mô tả'}
                    </p>
                    <p className="flex flex-wrap items-center gap-x-1.5 text-xs text-muted-foreground">
                      <span>Mặc định <code>{JSON.stringify(variable.default)}</code></span>
                      {limits ? <span>· {limits}</span> : null}
                      <span aria-hidden>·</span>
                      {used.length ? (
                        <button
                          type="button"
                          className="text-primary hover:underline"
                          aria-expanded={usageOpen === variable.name}
                          onClick={() => setUsageOpen(usageOpen === variable.name ? null : variable.name)}
                        >
                          dùng ở {used.length} node
                        </button>
                      ) : <span>chưa dùng</span>}
                    </p>
                    {usageOpen === variable.name ? (
                      <ul className="flex flex-wrap gap-1 pt-1">
                        {used.map((id) => (
                          <li key={id}>
                            <button
                              type="button"
                              className="rounded border px-1.5 py-0.5 text-xs hover:bg-muted"
                              onClick={() => { onJumpToNode(id); onOpenChange(false); }}
                            >
                              {titleOf(id)}
                            </button>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </li>
                );
              })}
              {!shown.length ? (
                <li className="px-3 py-6 text-center text-sm text-muted-foreground">{variables.length ? 'Không có biến khớp.' : 'Chưa có biến nào.'}</li>
              ) : null}
            </ul>
            <p className="text-xs text-muted-foreground">{variables.length}/{MAX_VARIABLES} biến</p>
          </div>
        ) : (
          <div className="space-y-4">
            {systemSpaces.map((space) => (
              <section key={space.name} className="space-y-1.5">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{space.title}</h3>
                {space.variables?.length ? (
                  <ul className="divide-y rounded-lg border">
                    {space.variables.map((variable) => (
                      <li key={variable.name} className="space-y-0.5 px-3 py-2">
                        <div className="flex items-center gap-2">
                          <code className="flex-1 text-sm">{space.name}.{variable.name}</code>
                          <span className="font-mono text-[11px] text-muted-foreground">{variable.type}{variable.nullable ? '?' : ''}</span>
                        </div>
                        {variable.description ? <p className="text-xs text-muted-foreground">{variable.description}</p> : null}
                        {variable.values?.length ? <p className="font-mono text-[11px] text-muted-foreground">{variable.values.join(' · ')}</p> : null}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    {space.source === 'profile_catalog'
                      ? 'Theo danh mục hồ sơ; gõ tên trường khi dùng (profile.<trường>).'
                      : space.source === 'node_output'
                        ? 'Output của các node chạy trước, dạng <id node>.<trường>.'
                        : 'Không có biến.'}
                  </p>
                )}
              </section>
            ))}
          </div>
        )}
      </SheetContent>

      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(value) => { if (!value) setPendingDelete(null); }}
        title={`Xoá conv.${pendingDelete ?? ''}?`}
        description="Biến chưa được node nào dùng."
        confirmLabel="Xoá biến"
        destructive
        onConfirm={() => {
          if (pendingDelete) onConfigChange({ ...config, workflow: removeVariable(workflow, pendingDelete) });
          setPendingDelete(null);
        }}
      />
      <ConfirmDialog
        open={pendingRename !== null}
        onOpenChange={(value) => { if (!value) setPendingRename(null); }}
        title={`Đổi tên conv.${pendingRename?.from.name ?? ''} thành conv.${pendingRename?.to.name ?? ''}?`}
        description={`Mọi tham chiếu trong ${pendingRename?.used.length ?? 0} node (${pendingRename?.used.map(titleOf).join(', ') ?? ''}) và trong persona case sẽ được đổi theo.`}
        confirmLabel={`Đổi tên ở ${pendingRename?.used.length ?? 0} node`}
        onConfirm={() => {
          if (pendingRename) finishSave(pendingRename.to, pendingRename.from);
          setPendingRename(null);
        }}
      />
    </Sheet>
  );
}
