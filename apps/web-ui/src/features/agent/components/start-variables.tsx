'use client';

import { Plus, Trash2, Variable } from 'lucide-react';
import { triggerUsage, variableUsage } from '../model/workflow/variable-usage';
import type { ChatflowWorkflow, NodeTypeCatalog } from '../types';
import { useVariablesPanel } from './variables-context';

const MAX_VARIABLES = 60;

function TypeTag({ type }: { type: string }) {
  return <span className="shrink-0 font-mono text-[11px] text-muted-foreground">{type}</span>;
}

/**
 * The start node panel: the conversation variables (shared by every flow; declared here, read and written by later
 * nodes) and the read-only system variables every node can read.
 */
export function StartVariables({ workflow, catalog }: { workflow: ChatflowWorkflow; catalog?: NodeTypeCatalog }) {
  const panel = useVariablesPanel();
  const variables = workflow.variables ?? [];
  // Usage counts every flow: the provider's view holds all of their nodes.
  const usageView = panel?.workflow ?? workflow;
  const editable = Boolean(panel && !panel.readOnly);
  const systemSpaces = (catalog?.namespaces ?? []).filter((space) => space.name !== 'conv' && space.name !== 'node');

  return (
    <>
      <section aria-label="Biến hội thoại" className="space-y-2 border-t px-4 py-4">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-semibold text-muted-foreground">
            BIẾN HỘI THOẠI <span className="font-normal">(conv.*) · {variables.length}/{MAX_VARIABLES}</span>
          </h4>
          {editable ? (
            <button
              type="button"
              aria-label="Thêm biến"
              disabled={variables.length >= MAX_VARIABLES}
              className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-40"
              onClick={() => panel!.edit(null)}
            >
              <Plus className="size-4" />
            </button>
          ) : null}
        </div>
        <p className="text-[11px] text-muted-foreground">Dùng chung cho mọi nghiệp vụ.</p>
        {variables.length ? (
          <ul className="space-y-1">
            {variables.map((variable) => {
              const used = variableUsage(usageView, variable.name);
              const triggers = triggerUsage(usageView, variable.name);
              const usedLabel = [used.length ? `${used.length} node` : '', triggers.length ? `${triggers.length} điều kiện kích hoạt` : '']
                .filter(Boolean).join(', ');
              return (
                <li key={variable.name} data-testid={`variable-${variable.name}`} className="group flex items-center gap-1 rounded-md border bg-card">
                  <button
                    type="button"
                    aria-label={`Sửa conv.${variable.name}`}
                    disabled={!editable}
                    title={variable.description}
                    className="flex min-w-0 flex-1 items-center gap-1.5 px-2.5 py-1.5 text-left text-sm hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-default disabled:hover:bg-transparent"
                    onClick={() => panel?.edit(variable.name)}
                  >
                    <Variable aria-hidden className="size-3.5 shrink-0 text-primary" />
                    <code className="shrink-0 text-xs font-medium">{variable.name}</code>
                    <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
                      · {variable.description || 'Chưa có mô tả'}
                    </span>
                    <span className="shrink-0 text-[11px] text-muted-foreground">{usedLabel ? `dùng ở ${usedLabel}` : 'chưa dùng'}</span>
                    <TypeTag type={variable.type} />
                  </button>
                  {editable ? (
                    <button
                      type="button"
                      aria-label={`Xoá conv.${variable.name}`}
                      disabled={Boolean(usedLabel)}
                      title={usedLabel ? `Đang dùng ở ${usedLabel}, không xoá được` : undefined}
                      className="mr-1 rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive disabled:pointer-events-none disabled:opacity-30"
                      onClick={() => panel!.remove(variable.name)}
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  ) : null}
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">Chưa có biến. Bấm + để khai báo biến mà các node sau đọc và ghi.</p>
        )}
      </section>

      <section aria-label="Biến hệ thống" className="space-y-3 border-t px-4 py-4">
        <h4 className="text-xs font-semibold text-muted-foreground">BIẾN HỆ THỐNG <span className="font-normal">(chỉ đọc)</span></h4>
        {systemSpaces.map((space) => (
          <div key={space.name} className="space-y-1">
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{space.title}</p>
            {space.variables?.length ? (
              <ul className="space-y-1">
                {space.variables.map((variable) => (
                  <li key={variable.name} title={variable.description} className="flex items-center gap-1.5 rounded-md bg-muted/50 px-2.5 py-1.5 text-sm">
                    <Variable aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />
                    <code className="shrink-0 text-xs">{space.name}.{variable.name}</code>
                    <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">{variable.description ? `· ${variable.description}` : ''}</span>
                    <TypeTag type={`${variable.type}${variable.nullable ? '?' : ''}`} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-muted-foreground">
                {space.source === 'profile_catalog' ? 'Theo danh mục hồ sơ; gõ tên trường khi dùng (profile.<trường>).' : 'Không có biến.'}
              </p>
            )}
          </div>
        ))}
      </section>
    </>
  );
}
