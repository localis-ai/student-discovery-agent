'use client';

import { useMemo, useState, type ReactNode } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { ConfirmDialog } from '@/features/knowledge';
import { removeVariable, renameVariable, upsertVariable, variableUsage } from '../model/workflow/variable-usage';
import type { AgentConfig, ChatflowVariable, ChatflowWorkflow, NodeTypeCatalog } from '../types';
import { VariableForm } from './variable-form';
import { VariablesPanelContext, type VariablesPanel } from './variables-context';

const EMPTY_WORKFLOW: ChatflowWorkflow = { entry: '', nodes: [] };

type Editing = { name: string | null; onCreated?: (name: string) => void } | null;
type PendingRename = { from: ChatflowVariable; to: ChatflowVariable; used: string[] } | null;

/**
 * Owns the conversation variables of a chatflow draft: the add/edit dialog, rename-everywhere and delete
 * confirmations. Renames touch persona cases too, so it works on the whole agent config.
 */
export function VariablesProvider({ config, catalog, readOnly = false, onConfigChange, onJumpToNode, children }: {
  config: AgentConfig;
  catalog?: NodeTypeCatalog;
  readOnly?: boolean;
  onConfigChange: (next: AgentConfig) => void;
  onJumpToNode: (nodeId: string) => void;
  children: ReactNode;
}) {
  // A draft without a renderable workflow still gets the provider: it then simply has no variables.
  const workflow = (config.workflow ?? EMPTY_WORKFLOW) as ChatflowWorkflow;
  const variables = workflow.variables ?? [];
  const [editing, setEditing] = useState<Editing>(null);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [pendingRename, setPendingRename] = useState<PendingRename>(null);
  const titleOf = (id: string) => workflow.nodes.find((node) => node.id === id)?.title?.trim() || id;
  const current = editing?.name ? variables.find((item) => item.name === editing.name) : undefined;

  const panel = useMemo<VariablesPanel>(() => ({
    workflow,
    catalog,
    readOnly,
    edit: (name, onCreated) => { if (!readOnly) setEditing({ name, onCreated }); },
    remove: (name) => { if (!readOnly) setPendingDelete(name); },
    jumpToNode: onJumpToNode,
  }), [workflow, catalog, readOnly, onJumpToNode]);

  const finishSave = (variable: ChatflowVariable, previous?: ChatflowVariable) => {
    let next = config;
    if (previous && previous.name !== variable.name) next = renameVariable(next, previous.name, variable.name);
    const updated = upsertVariable(next.workflow as ChatflowWorkflow, variable, previous ? variable.name : undefined);
    onConfigChange({ ...next, workflow: updated });
    if (!previous) editing?.onCreated?.(variable.name);
    setEditing(null);
  };
  const save = (variable: ChatflowVariable) => {
    if (current && current.name !== variable.name) {
      const used = variableUsage(workflow, current.name);
      if (used.length) {
        setPendingRename({ from: current, to: variable, used });
        return;
      }
    }
    finishSave(variable, current);
  };

  return (
    <VariablesPanelContext.Provider value={panel}>
      {children}
      <Dialog open={editing !== null && !pendingRename} onOpenChange={(open) => { if (!open) setEditing(null); }}>
        <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
          <DialogTitle>{current ? `Sửa biến conv.${current.name}` : 'Thêm biến hội thoại'}</DialogTitle>
          <DialogDescription className="text-sm text-muted-foreground">
            Biến hội thoại được nhớ qua các lượt chat; node Gán biến ghi, các node khác đọc bằng conv.&lt;tên&gt;.
          </DialogDescription>
          {editing ? (
            <VariableForm
              key={editing.name ?? 'new'}
              initial={current}
              others={variables}
              onSave={save}
              onCancel={() => setEditing(null)}
            />
          ) : null}
        </DialogContent>
      </Dialog>
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
    </VariablesPanelContext.Provider>
  );
}
