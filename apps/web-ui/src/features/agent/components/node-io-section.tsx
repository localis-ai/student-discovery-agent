'use client';

import { ArrowRight, Variable } from 'lucide-react';
import { describeInput, nodeInputs, nodeOutputs, type InputSource } from '../model/workflow/node-io';
import type { ChatflowNode, ChatflowWorkflow, NodeTypeCatalog } from '../types';
import { NodeIcon } from './node-visuals';
import { useVariablesPanel } from './variables-context';

function SourceChip({ input }: { input: InputSource }) {
  return (
    // The path beside it already names the field: the chip only says where the value comes from.
    <span className="inline-flex min-w-0 max-w-[45%] shrink items-center gap-1 rounded-md border bg-background px-1.5 py-0.5 text-[11px]">
      {input.nodeType ? <NodeIcon type={input.nodeType} size="sm" className="size-4 rounded" /> : <Variable aria-hidden className="size-3 text-muted-foreground" />}
      <span className="truncate text-muted-foreground">{input.source}</span>
    </span>
  );
}

/** What a node reads (with where each value comes from) and what it makes available to later nodes. */
export function NodeIoSection({ node, workflow, catalog, showOutputs = true }: {
  node: ChatflowNode; workflow: ChatflowWorkflow; catalog?: NodeTypeCatalog; showOutputs?: boolean;
}) {
  const panel = useVariablesPanel();
  const inputs = nodeInputs(node).map((path) => describeInput(path, workflow, catalog));
  const outputs = showOutputs ? nodeOutputs(node, catalog) : [];
  if (!inputs.length && !outputs.length) return null;

  const open = (input: InputSource) => {
    if (!panel) return;
    if (input.kind === 'conv' && workflow.variables?.some((variable) => variable.name === input.field)) panel.edit(input.field);
    else if (input.kind === 'node' && input.nodeId) panel.jumpToNode(input.nodeId);
  };
  const actionable = (input: InputSource) => Boolean(panel) && (input.kind === 'node'
    || (input.kind === 'conv' && !panel!.readOnly && Boolean(workflow.variables?.some((variable) => variable.name === input.field))));

  return (
    <>
      {inputs.length ? (
        <section aria-label="Biến đầu vào" className="space-y-2 border-t px-4 py-4">
          <h4 className="text-xs font-semibold text-muted-foreground">BIẾN ĐẦU VÀO <span className="font-normal">(node này đọc)</span></h4>
          <ul className="space-y-1">
            {inputs.map((input) => {
              const row = (
                <>
                  <code className="min-w-0 flex-1 truncate text-xs" title={input.path}>{input.path}</code>
                  <SourceChip input={input} />
                  {input.type ? <span className="shrink-0 font-mono text-[11px] text-muted-foreground">{input.type}</span> : null}
                  {input.kind === 'unknown' ? <span className="shrink-0 text-[11px] text-destructive">không rõ nguồn</span> : null}
                </>
              );
              return (
                <li key={input.path} title={input.description}>
                  {actionable(input) ? (
                    <button
                      type="button"
                      aria-label={input.kind === 'node' ? `Tới node ${input.source}` : `Sửa ${input.path}`}
                      className="flex w-full items-center gap-2 rounded-md border bg-card px-2.5 py-1.5 text-left hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      onClick={() => open(input)}
                    >
                      {row}
                    </button>
                  ) : (
                    <div className="flex items-center gap-2 rounded-md bg-muted/50 px-2.5 py-1.5">{row}</div>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
      {outputs.length ? (
        <section aria-label="Biến đầu ra" className="space-y-2 border-t px-4 py-4">
          <h4 className="text-xs font-semibold text-muted-foreground">BIẾN ĐẦU RA <span className="font-normal">(node sau đọc được)</span></h4>
          <ul className="space-y-1">
            {outputs.map((output) => (
              <li key={output.path} className="flex items-center gap-2 rounded-md bg-muted/50 px-2.5 py-1.5" title={output.values?.join(' · ')}>
                <ArrowRight aria-hidden className="size-3 shrink-0 text-muted-foreground" />
                <code className="min-w-0 flex-1 truncate text-xs">{output.path}</code>
                {output.type ? <span className="shrink-0 font-mono text-[11px] text-muted-foreground">{output.type}</span> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}
