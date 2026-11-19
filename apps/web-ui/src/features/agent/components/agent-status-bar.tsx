'use client';

import { ChevronDown, History } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { relativeTime } from '@/features/knowledge';
import { cn } from '@/lib/utils/cn';
import type { AgentActive } from '../types';

export type DraftState = 'unsaved' | 'differs' | 'same';
const LABEL: Record<DraftState, string> = { unsaved: 'Chưa lưu', differs: 'Đã lưu – khác bản đang dùng', same: 'Trùng bản đang dùng' };
// Unsaved edits need attention; a saved draft ahead of the live copy is waiting to be published; equal is settled.
const DOT: Record<DraftState, string> = { unsaved: 'bg-status-warning', differs: 'bg-primary', same: 'bg-status-success' };

function DraftStateLabel({ state }: { state: DraftState }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
      <span aria-hidden className={cn('size-2 shrink-0 rounded-full', DOT[state])} />
      <span data-testid="draft-state">{LABEL[state]}</span>
    </span>
  );
}

/** Publish, with the live copy one click away beside it (split button), instead of a status line of its own. */
function PublishButton({ active, disabled, onPublish, onShowVersions }: {
  active: AgentActive | null | undefined; disabled: boolean; onPublish: () => void; onShowVersions?: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex">
      <Button size="sm" className="rounded-r-none" disabled={disabled} onClick={onPublish}>Phát hành</Button>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button size="sm" aria-label="Bản đang dùng" className="rounded-l-none border-l border-primary-foreground/25 px-2">
            <ChevronDown className="size-4" aria-hidden />
          </Button>
        </PopoverTrigger>
        <PopoverContent align="end" className="w-72 space-y-3 p-4">
          {active ? (
            <div>
              <p className="text-sm font-semibold">Đang dùng v{active.version}</p>
              <p className="text-sm text-muted-foreground">Phát hành {relativeTime(active.updated_at).toLocaleLowerCase('vi')} bởi {active.updated_by}</p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Chưa có bản phát hành.</p>
          )}
          {onShowVersions && (
            <Button size="sm" variant="outline" className="w-full" onClick={() => { setOpen(false); onShowVersions(); }}>
              <History className="size-4" aria-hidden /> Xem lịch sử phiên bản
            </Button>
          )}
        </PopoverContent>
      </Popover>
    </div>
  );
}

export function AgentStatusBar({ active, draftState, busy, canPublish, onSave, onValidate, onPublish, onShowVersions, title, center, compact = false }: {
  active: AgentActive | null | undefined; draftState: DraftState; busy: boolean; canPublish: boolean;
  onSave: () => void; onValidate: () => void; onPublish: () => void; onShowVersions?: () => void;
  /** Page heading shown above the draft state (full bar only). */
  title?: ReactNode;
  /** Controls between the heading and the actions, e.g. view tabs. */
  center?: ReactNode;
  /** Inline in another header (the chatflow editor) instead of the sticky page header. */
  compact?: boolean;
}) {
  const actions = (
    <div className="flex gap-2">
      <Button variant="outline" size="sm" disabled={busy || draftState !== 'unsaved'} onClick={onSave}>Lưu nháp</Button>
      <Button variant="outline" size="sm" disabled={busy} onClick={onValidate}>Kiểm tra</Button>
      <PublishButton active={active} disabled={busy || !canPublish || draftState !== 'differs'} onPublish={onPublish} onShowVersions={onShowVersions} />
    </div>
  );
  if (compact) {
    return <div className="flex flex-wrap items-center gap-3"><DraftStateLabel state={draftState} />{actions}</div>;
  }
  return (
    // One header row: heading and state on the left, view tabs, then the draft actions on the right.
    <div className="sticky top-0 z-10 -mx-4 -mt-4 flex flex-wrap items-center gap-x-6 gap-y-3 border-b bg-background/95 px-4 py-3 backdrop-blur md:-mx-6 md:-mt-6 md:px-6">
      <div className="mr-auto min-w-0">
        {title && <h1 className="text-lg font-semibold leading-7">{title}</h1>}
        <DraftStateLabel state={draftState} />
      </div>
      {center}
      {actions}
    </div>
  );
}
