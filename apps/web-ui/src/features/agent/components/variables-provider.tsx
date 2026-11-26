'use client';

import { useMemo, useState, type ReactNode } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { ConfirmDialog } from '@/features/knowledge';
import { allFlowsView, isRenderableChatflow } from '../model/workflow/flows';
import {
  personaCaseUsage, removeFromPersonaCases, removeVariable, renameVariable, triggerUsage, upsertVariable, variableUsage,
} from '../model/workflow/variable-usage';
import type { AgentConfig, ChatflowVariable, ChatflowWorkflow, NodeTypeCatalog } from '../types';
import { VariableForm } from './variable-form';
import { VariablesPanelContext, type VariablesPanel } from './variables-context';

const EMPTY_WORKFLOW: ChatflowWorkflow = { entry: '', nodes: [] };

type Editing = { name: string | null; onCreated?: (name: string) => void } | null;
type PendingRename = { from: ChatflowVariable; to: ChatflowVariable; used: string[]; triggers: string[] } | null;

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
  // Variables are shared by every flow: usage, renames and removals look at all of them as one node list.
  // A draft without a renderable chatflow still gets the provider: it then simply has no variables.
  const chat = isRenderableChatflow(config.workflow) ? config.workflow : undefined;
  const workflow = useMemo(() => (chat ? allFlowsView(chat) : EMPTY_WORKFLOW), [chat]);
  const writeVariables = (next: AgentConfig, view: ChatflowWorkflow): AgentConfig =>
    (isRenderableChatflow(next.workflow) ? { ...next, workflow: { ...next.workflow, variables: view.variables ?? [] } } : next);
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

  const deletingCases = pendingDelete ? personaCaseUsage(config.persona_cases, pendingDelete) : [];
  const finishSave = (variable: ChatflowVariable, previous?: ChatflowVariable) => {
    let next = config;
    if (previous && previous.name !== variable.name) next = renameVariable(next, previous.name, variable.name);
    const view = isRenderableChatflow(next.workflow) ? allFlowsView(next.workflow) : EMPTY_WORKFLOW;
    onConfigChange(writeVariables(next, upsertVariable(view, variable, previous ? variable.name : undefined)));
    if (!previous) editing?.onCreated?.(variable.name);
    setEditing(null);
  };
  const save = (variable: ChatflowVariable) => {
    if (current && current.name !== variable.name) {
      const used = variableUsage(workflow, current.name);
      const triggers = triggerUsage(workflow, current.name);
      if (used.length || triggers.length) {
        setPendingRename({ from: current, to: variable, used, triggers });
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
        description={deletingCases.length
          ? `Biến chưa được node nào dùng. Giá trị của biến trong persona case ${deletingCases.join(', ')} cũng sẽ bị xoá.`
          : 'Biến chưa được node nào dùng.'}
        confirmLabel="Xoá biến"
        destructive
        onConfirm={() => {
          if (pendingDelete) {
            const next = removeFromPersonaCases(config, pendingDelete);
            onConfigChange(writeVariables(next, removeVariable(workflow, pendingDelete)));
          }
          setPendingDelete(null);
        }}
      />
      <ConfirmDialog
        open={pendingRename !== null}
        onOpenChange={(value) => { if (!value) setPendingRename(null); }}
        title={`Đổi tên conv.${pendingRename?.from.name ?? ''} thành conv.${pendingRename?.to.name ?? ''}?`}
        description={`Mọi tham chiếu trong ${pendingRename?.used.length ?? 0} node (${pendingRename?.used.map(titleOf).join(', ') ?? ''})${
          pendingRename?.triggers.length ? `, điều kiện kích hoạt của ${pendingRename.triggers.join(', ')}` : ''} và trong persona case sẽ được đổi theo.`}
        confirmLabel={`Đổi tên ở ${pendingRename?.used.length ?? 0} node`}
        onConfirm={() => {
          if (pendingRename) finishSave(pendingRename.to, pendingRename.from);
          setPendingRename(null);
        }}
      />
    </VariablesPanelContext.Provider>
  );
}
