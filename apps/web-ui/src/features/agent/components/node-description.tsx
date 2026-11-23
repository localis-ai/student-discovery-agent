'use client';

import { useLayoutEffect, useRef, useState } from 'react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';

/**
 * A node's authoring note on its canvas card: one line, and a small "Xem thêm" that opens the whole note when it
 * does not fit. `nodrag nopan` and stopPropagation keep the click from selecting or dragging the node.
 */
export function NodeDescription({ text, forceOverflow = false }: { text: string; forceOverflow?: boolean }) {
  const ref = useRef<HTMLParagraphElement>(null);
  const [overflows, setOverflows] = useState(forceOverflow);
  useLayoutEffect(() => {
    const element = ref.current;
    if (element && !forceOverflow) setOverflows(element.scrollWidth > element.clientWidth);
  }, [text, forceOverflow]);
  return (
    <div className="flex min-w-0 items-baseline gap-1 px-3 pt-1.5">
      <p ref={ref} data-testid="node-description" className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
        {text}
      </p>
      {overflows ? (
        <Popover>
          <PopoverTrigger asChild>
            <button
              type="button"
              aria-label="Xem thêm mô tả"
              className="nodrag nopan shrink-0 rounded px-1 text-[11px] font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onClick={(event) => event.stopPropagation()}
              onPointerDown={(event) => event.stopPropagation()}
            >
              Xem thêm
            </button>
          </PopoverTrigger>
          <PopoverContent
            role="dialog"
            aria-label="Mô tả node"
            className="nodrag nopan max-w-xs whitespace-pre-wrap text-sm"
            onClick={(event) => event.stopPropagation()}
          >
            {text}
          </PopoverContent>
        </Popover>
      ) : null}
    </div>
  );
}
