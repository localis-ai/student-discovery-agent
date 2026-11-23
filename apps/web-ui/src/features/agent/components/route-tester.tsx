'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useDebugRun } from '../hooks/use-debug-run';
import { ROUTE_METHODS, findFlow } from '../model/workflow/flows';
import type { Chatflow } from '../types';

/** Types one student message and shows which flow the router would pick, without running the flow. */
export function RouteTester({ chat, beforeRun, onRouted }: {
  chat: Chatflow;
  /** Saves the draft first: the run reads the saved copy. */
  beforeRun?: () => Promise<boolean>;
  onRouted?: (flowId: string | null) => void;
}) {
  const [message, setMessage] = useState('');
  // Mid-conversation by default: a first-turn trigger (e.g. a welcome flow) would otherwise win every test.
  const [firstTurn, setFirstTurn] = useState(false);
  const debug = useDebugRun(beforeRun);
  const route = debug.result?.route ?? null;
  const run = async () => {
    if (!message.trim()) return;
    onRouted?.(null);
    await debug.run({ message: message.trim(), stop_after: 'route', state: { turn_index: firstTurn ? 0 : 1 } });
  };
  const shown = route ? findFlow(chat, route.flow) : undefined;
  const routedFlow = route?.flow ?? null;
  useEffect(() => { if (routedFlow) onRouted?.(routedFlow); }, [routedFlow, onRouted]);

  return (
    <section aria-label="Thử định tuyến" className="space-y-2 rounded-lg border bg-card p-3">
      <div>
        <h4 className="text-sm font-semibold">Thử định tuyến</h4>
        <p className="text-xs text-muted-foreground">Gõ một câu của học sinh để xem router chọn nghiệp vụ nào. Chỉ chạy bước định tuyến, không chạy nghiệp vụ.</p>
      </div>
      <form className="flex gap-2" onSubmit={event => { event.preventDefault(); void run(); }}>
        <Input aria-label="Câu thử định tuyến" value={message} maxLength={4000} onChange={event => setMessage(event.target.value)}
          placeholder="học phí ngành CNTT bao nhiêu?" />
        <Button type="submit" size="sm" className="h-9" disabled={debug.running || !message.trim()}>
          {debug.running ? 'Đang chạy…' : 'Thử'}
        </Button>
      </form>
      <label className="flex items-center gap-2 text-xs text-muted-foreground">
        <input type="checkbox" checked={firstTurn} onChange={event => setFirstTurn(event.target.checked)} />
        Mô phỏng lượt đầu tiên của hội thoại (để thử điều kiện kích hoạt như lời chào)
      </label>
      {debug.error ? <p role="alert" className="text-xs text-destructive">{debug.error}</p> : null}
      {route ? (
        <p role="status" className="rounded-md bg-muted/60 p-2 text-sm">
          → <strong>{shown?.title ?? route.flow}</strong>
          <span className="text-muted-foreground"> · {ROUTE_METHODS[route.method] ?? route.method}</span>
          {route.label && route.label !== route.flow ? <span className="text-muted-foreground"> (nhãn {route.label})</span> : null}
        </p>
      ) : null}
    </section>
  );
}
