'use client';

import { useId, useMemo, useState, type ReactNode } from 'react';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils/cn';
import { VARIABLE_PATH } from '../model/workflow/condition';
import type { VariableGroup, VariableInfo } from '../model/workflow/variables';

/**
 * Grouped variable combobox (WAI-ARIA combobox + listbox). The input stays a free text field, so a path the catalog
 * does not list (profile.*) can still be typed; every keystroke reports the typed path, as the old datalist did.
 */
export function VariablePicker({ id, label, value, groups, disabled, onChange, placeholder = 'sys.query', invalid, footer }: {
  id: string;
  label: string;
  value: string;
  groups: VariableGroup[];
  disabled: boolean;
  onChange: (path: string) => void;
  placeholder?: string;
  invalid?: boolean;
  /** Extra action under the list, e.g. "+ Khai báo biến mới…"; the list closes when it runs. */
  footer?: { label: string; onSelect: () => void };
}) {
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState<string | null>(null);
  const [active, setActive] = useState(-1);
  const needle = (query ?? '').toLowerCase();
  const filtered = useMemo(
    () => groups
      .map((group) => ({
        ...group,
        items: group.items.filter((item) => !needle || item.path.toLowerCase().includes(needle)
          || (item.description ?? '').toLowerCase().includes(needle)),
      }))
      .filter((group) => group.items.length),
    [groups, needle],
  );
  const flat: VariableInfo[] = filtered.flatMap((group) => group.items);
  const typed = (query ?? '').trim();
  const custom = typed && VARIABLE_PATH.test(typed) && !flat.some((item) => item.path === typed) ? typed : null;
  const optionId = (index: number) => `${listId}-opt-${index}`;
  const close = () => {
    setOpen(false);
    setQuery(null);
    setActive(-1);
  };
  const choose = (path: string) => {
    onChange(path);
    close();
  };

  return (
    <div className="relative min-w-0 flex-1">
      <Input
        id={id}
        role="combobox"
        aria-label={label}
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={open && active >= 0 ? optionId(active) : undefined}
        autoComplete="off"
        placeholder={placeholder}
        className={cn('h-8 font-mono text-xs', invalid && 'border-destructive')}
        value={query ?? value}
        disabled={disabled}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(close, 120)}
        onChange={(event) => {
          const next = event.target.value.trim();
          setQuery(next);
          setOpen(true);
          setActive(-1);
          onChange(next);
        }}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown') {
            event.preventDefault();
            setOpen(true);
            setActive((index) => Math.min(index + 1, flat.length - 1));
          } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            setActive((index) => Math.max(index - 1, 0));
          } else if (event.key === 'Enter' && open && flat[active]) {
            event.preventDefault();
            choose(flat[active]!.path);
          } else if (event.key === 'Escape') {
            close();
          }
        }}
      />
      {open && !disabled ? (
        <div
          id={listId}
          role="listbox"
          aria-label={label}
          className="absolute left-0 right-0 z-20 mt-1 max-h-72 overflow-y-auto rounded-md border bg-popover p-1 text-popover-foreground shadow-md"
        >
          {filtered.map((group) => (
            <div key={group.title} role="group" aria-label={group.title}>
              <div className="px-2 pb-0.5 pt-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{group.title}</div>
              {group.items.map((item) => {
                const index = flat.indexOf(item);
                return (
                  <Row key={item.path} id={optionId(index)} active={index === active} selected={item.path === value} onPick={() => choose(item.path)}>
                    <span className="flex items-center justify-between gap-2">
                      <span className="truncate font-mono text-xs">{item.path}</span>
                      {item.type ? <span className="shrink-0 text-[11px] text-muted-foreground">{item.type}</span> : null}
                    </span>
                    {item.description ? <span className="block truncate text-[11px] text-muted-foreground">{item.description}</span> : null}
                  </Row>
                );
              })}
            </div>
          ))}
          {custom ? (
            <Row id={`${listId}-custom`} active={false} selected={false} onPick={() => choose(custom)}>
              <span className="text-xs">Dùng <code>{custom}</code></span>
            </Row>
          ) : null}
          {!filtered.length && !custom ? <p className="px-2 py-1.5 text-xs text-muted-foreground">Không có biến khớp.</p> : null}
          {footer ? (
            <button
              type="button"
              className="mt-1 w-full rounded-sm border-t px-2 py-1.5 text-left text-xs font-medium text-primary hover:bg-muted"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                close();
                footer.onSelect();
              }}
            >
              {footer.label}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Row({ id, active, selected, onPick, children }: {
  id: string; active: boolean; selected: boolean; onPick: () => void; children: ReactNode;
}) {
  return (
    <div
      id={id}
      role="option"
      aria-selected={selected}
      className={cn('cursor-pointer rounded-sm px-2 py-1', active ? 'bg-muted' : 'hover:bg-muted/60')}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onPick}
    >
      {children}
    </div>
  );
}
