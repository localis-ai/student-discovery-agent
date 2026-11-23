'use client';

import { Route, Star } from 'lucide-react';
import { gotoLinks } from '../model/workflow/flows';
import type { Chatflow } from '../types';

const ROW = 56;
const TOP = 28;
const FLOW_X = 200;
const WIDTH = 440;

/**
 * Read-only map of how a turn reaches each flow: the router on the left, one row per flow in trigger order, a line
 * per way in (trigger, router description, default) and dashed arcs for goto_flow between flows.
 */
export function FlowMap({ chat, highlight }: { chat: Chatflow; highlight?: string | null }) {
  const height = TOP * 2 + Math.max(chat.flows.length - 1, 0) * ROW;
  const routerY = height / 2;
  const rowY = (index: number) => TOP + index * ROW;
  const indexOf = new Map(chat.flows.map((flow, index) => [flow.id, index]));
  const links = gotoLinks(chat).filter(link => indexOf.has(link.to) && link.from !== link.to);

  return (
    <figure aria-label="Sơ đồ định tuyến" className="overflow-x-auto rounded-lg border bg-card p-3">
      <div className="relative" style={{ width: WIDTH, height }}>
        <svg aria-hidden width={WIDTH} height={height} className="absolute inset-0 text-border">
          {chat.flows.map((flow, index) => {
            const way = flow.trigger ? 'trigger' : flow.routable === false ? null : 'route';
            const y = rowY(index);
            const active = highlight === flow.id;
            return way ? (
              <path key={flow.id} d={`M 112 ${routerY} C 156 ${routerY}, 156 ${y}, ${FLOW_X} ${y}`} fill="none"
                strokeWidth={active ? 2.5 : 1.5}
                className={active ? 'stroke-primary' : way === 'trigger' ? 'stroke-amber-500' : 'stroke-current'} />
            ) : null;
          })}
          {links.map(link => {
            const from = rowY(indexOf.get(link.from)!);
            const to = rowY(indexOf.get(link.to)!);
            const bend = WIDTH - 8;
            return (
              <path key={link.nodeId} d={`M ${WIDTH - 24} ${from} C ${bend} ${from}, ${bend} ${to}, ${WIDTH - 24} ${to}`}
                fill="none" strokeDasharray="4 3" strokeWidth={1.5} className="stroke-cyan-600" />
            );
          })}
        </svg>
        <div className="absolute flex h-10 w-28 items-center justify-center gap-1.5 rounded-lg border bg-muted text-xs font-medium"
          style={{ left: 0, top: routerY - 20 }}>
          <Route aria-hidden className="size-3.5" /> Router
        </div>
        <ol>
          {chat.flows.map((flow, index) => (
            <li key={flow.id} data-testid={`flow-map-${flow.id}`}
              className={`absolute flex h-10 items-center gap-1.5 truncate rounded-lg border px-3 text-xs ${highlight === flow.id ? 'border-primary bg-primary-subtle' : 'bg-background'}`}
              style={{ left: FLOW_X, top: rowY(index) - 20, width: WIDTH - FLOW_X - 24 }}>
              <span className="font-mono text-muted-foreground">{index + 1}</span>
              <span className="truncate font-medium">{flow.title}</span>
              {chat.router.default_flow === flow.id ? <Star aria-label="mặc định" className="size-3 shrink-0 fill-amber-400 text-amber-400" /> : null}
            </li>
          ))}
        </ol>
      </div>
      <figcaption className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
        <span><span aria-hidden className="mr-1 inline-block h-0.5 w-4 bg-amber-500 align-middle" />điều kiện kích hoạt</span>
        <span><span aria-hidden className="mr-1 inline-block h-0.5 w-4 bg-border align-middle" />router chọn theo mô tả</span>
        <span><span aria-hidden className="mr-1 inline-block h-0.5 w-4 border-t border-dashed border-cyan-600 align-middle" />chuyển nghiệp vụ</span>
        <span>★ mặc định</span>
      </figcaption>
    </figure>
  );
}
