'use client';

import { X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils/cn';
import {
  CONSTRAINT_KEYS,
  MAX_VARIABLE_DESCRIPTION,
  variableDeclarationErrors,
  type DeclarationField,
} from '../model/workflow/variable-rules';
import type { ChatflowVariable, VariableConstraints, VariableType } from '../types';

const TYPES: VariableType[] = ['string', 'number', 'boolean', 'enum', 'string_list'];
const EMPTY_DEFAULT: Record<VariableType, unknown> = { string: '', number: 0, boolean: false, enum: '', string_list: [] };
type NumericConstraint = Exclude<keyof VariableConstraints, 'integer'>;

function defaultText(type: VariableType, value: unknown): string {
  if (type === 'string_list') return Array.isArray(value) ? value.join('\n') : '';
  return value === undefined || value === null ? '' : String(value);
}

function parseDefault(type: VariableType, text: string): unknown {
  if (type === 'number') return text.trim() === '' ? Number.NaN : Number(text);
  if (type === 'boolean') return text === 'true';
  if (type === 'string_list') return text.split('\n').map((line) => line.trim()).filter(Boolean);
  return text;
}

/** Only the constraint keys the type accepts, with unset ones dropped; undefined when nothing is left. */
function cleanConstraints(type: VariableType, raw: VariableConstraints): VariableConstraints | undefined {
  const kept = Object.fromEntries(Object.entries(raw).filter(([key, value]) =>
    CONSTRAINT_KEYS[type].includes(key as keyof VariableConstraints)
    && value !== undefined && value !== false && !(typeof value === 'number' && Number.isNaN(value))));
  return Object.keys(kept).length ? (kept as VariableConstraints) : undefined;
}

/** Declares or edits one conversation variable: name, description, type, constraints and default. */
export function VariableForm({ initial, others, onSave, onCancel }: {
  initial?: ChatflowVariable;
  others: ChatflowVariable[];
  onSave: (variable: ChatflowVariable) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [type, setType] = useState<VariableType>(initial?.type ?? 'string');
  const [values, setValues] = useState<string[]>(initial?.values ?? []);
  const [pending, setPending] = useState('');
  const [constraints, setConstraints] = useState<VariableConstraints>(initial?.constraints ?? {});
  const [defaultValue, setDefaultValue] = useState(defaultText(initial?.type ?? 'string', initial?.default ?? ''));
  const [touched, setTouched] = useState<ReadonlySet<string>>(new Set());

  const variable = useMemo<ChatflowVariable>(() => {
    const next: ChatflowVariable = { name: name.trim(), type, default: parseDefault(type, defaultValue) };
    if (description.trim()) next.description = description.trim();
    if (type === 'enum') next.values = values;
    const kept = cleanConstraints(type, constraints);
    if (kept) next.constraints = kept;
    return next;
  }, [name, description, type, values, constraints, defaultValue]);
  const errors = variableDeclarationErrors(variable, others.filter((other) => other.name !== initial?.name));
  const valid = Object.keys(errors).length === 0;
  const touch = (field: string) => setTouched((current) => new Set(current).add(field));
  const shown = (field: DeclarationField) => (touched.has(field) || touched.has('*') ? errors[field] : undefined);
  const errorText = (field: DeclarationField, id: string) => {
    const message = shown(field);
    return message ? <p id={`${id}-error`} role="alert" className="text-xs text-destructive">{message}</p> : null;
  };

  const changeType = (next: VariableType) => {
    setType(next);
    setDefaultValue(defaultText(next, EMPTY_DEFAULT[next]));
  };
  const setNumber = (key: NumericConstraint, text: string) => {
    setConstraints((current) => ({ ...current, [key]: text.trim() === '' ? undefined : Number(text) }));
    touch(`constraints.${key}`);
  };
  const addValue = () => {
    const value = pending.trim();
    if (value && !values.includes(value)) setValues([...values, value]);
    setPending('');
    if (value) touch('values');
  };

  return (
    <form
      className="space-y-4 rounded-lg border bg-muted/30 p-3"
      onSubmit={(event) => {
        event.preventDefault();
        setTouched(new Set(['*']));
        if (valid) onSave(variable);
      }}
    >
      <div className="space-y-1.5">
        <Label htmlFor="variable-name">Tên biến</Label>
        <div className="flex items-center">
          <span aria-hidden className="rounded-l-md border border-r-0 bg-muted px-2 py-2 font-mono text-xs text-muted-foreground">conv.</span>
          <Input
            id="variable-name"
            aria-label="Tên biến"
            aria-invalid={Boolean(shown('name'))}
            aria-describedby={shown('name') ? 'variable-name-error' : 'variable-name-hint'}
            className="rounded-l-none font-mono text-sm"
            autoComplete="off"
            value={name}
            onChange={(event) => { setName(event.target.value); touch('name'); }}
          />
        </div>
        {errorText('name', 'variable-name') ?? (
          <p id="variable-name-hint" className="text-xs text-muted-foreground">Chữ thường, số, gạch dưới; bắt đầu bằng chữ; tối đa 40 ký tự.</p>
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="variable-description">Mô tả</Label>
        <Textarea
          id="variable-description"
          aria-label="Mô tả"
          rows={2}
          maxLength={MAX_VARIABLE_DESCRIPTION}
          placeholder="Biến này lưu gì, node nào ghi, node nào đọc…"
          value={description}
          onChange={(event) => { setDescription(event.target.value); touch('description'); }}
        />
        {errorText('description', 'variable-description')}
      </div>

      <fieldset className="space-y-1.5">
        <legend className="text-sm font-medium">Kiểu dữ liệu</legend>
        <div role="radiogroup" aria-label="Kiểu dữ liệu" className="flex flex-wrap gap-1.5">
          {TYPES.map((option) => (
            <label
              key={option}
              className={cn(
                'cursor-pointer rounded-md border px-2.5 py-1 font-mono text-xs has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring',
                type === option ? 'border-primary bg-primary-subtle text-primary' : 'hover:bg-muted',
              )}
            >
              <input type="radio" name="variable-type" className="sr-only" aria-label={option} checked={type === option} onChange={() => changeType(option)} />
              {option}
            </label>
          ))}
        </div>
      </fieldset>

      {type === 'enum' ? (
        <div className="space-y-1.5">
          <span className="text-sm font-medium">Giá trị cho phép</span>
          {values.length ? (
            <div className="flex flex-wrap gap-1.5">
              {values.map((value) => (
                <span key={value} className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
                  {value}
                  <button
                    type="button"
                    aria-label={`Bỏ giá trị ${value}`}
                    className="rounded hover:text-destructive"
                    onClick={() => { setValues(values.filter((item) => item !== value)); touch('values'); }}
                  >
                    <X className="size-3" />
                  </button>
                </span>
              ))}
            </div>
          ) : null}
          <Input
            aria-label="Thêm giá trị"
            placeholder="Gõ giá trị rồi nhấn Enter"
            className="h-8 font-mono text-xs"
            value={pending}
            onChange={(event) => setPending(event.target.value)}
            onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); addValue(); } }}
            onBlur={addValue}
          />
          {errorText('values', 'variable-values')}
        </div>
      ) : null}

      {CONSTRAINT_KEYS[type].length ? (
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">
            Ràng buộc <span className="font-normal text-muted-foreground">(tùy chọn)</span>
          </legend>
          <div className="grid grid-cols-2 gap-2">
            {type === 'string' ? (
              <>
                <NumberBox label="Độ dài tối thiểu" value={constraints.min_length} onChange={(text) => setNumber('min_length', text)} error={shown('constraints.min_length')} />
                <NumberBox label="Độ dài tối đa" value={constraints.max_length} onChange={(text) => setNumber('max_length', text)} />
              </>
            ) : null}
            {type === 'number' ? (
              <>
                <NumberBox label="Tối thiểu" value={constraints.minimum} onChange={(text) => setNumber('minimum', text)} error={shown('constraints.minimum')} />
                <NumberBox label="Tối đa" value={constraints.maximum} onChange={(text) => setNumber('maximum', text)} />
                <label className="col-span-2 flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    aria-label="Số nguyên"
                    checked={Boolean(constraints.integer)}
                    onChange={(event) => setConstraints((current) => ({ ...current, integer: event.target.checked || undefined }))}
                  />
                  Số nguyên
                </label>
              </>
            ) : null}
            {type === 'string_list' ? (
              <>
                <NumberBox label="Số phần tử tối đa" value={constraints.max_items} onChange={(text) => setNumber('max_items', text)} />
                <NumberBox label="Độ dài mỗi phần tử tối đa" value={constraints.item_max_length} onChange={(text) => setNumber('item_max_length', text)} />
              </>
            ) : null}
          </div>
        </fieldset>
      ) : null}

      <div className="space-y-1.5">
        <Label htmlFor="variable-default">Giá trị mặc định</Label>
        {type === 'enum' || type === 'boolean' ? (
          <select
            id="variable-default"
            aria-label="Giá trị mặc định"
            className="h-9 w-full rounded-md border border-input bg-background px-3 font-mono text-sm"
            value={defaultValue}
            onChange={(event) => { setDefaultValue(event.target.value); touch('default'); }}
          >
            {type === 'enum' ? <option value="">Chọn giá trị…</option> : null}
            {(type === 'enum' ? values : ['true', 'false']).map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        ) : type === 'string_list' ? (
          <Textarea
            id="variable-default"
            aria-label="Giá trị mặc định"
            rows={3}
            className="font-mono text-xs"
            placeholder="Mỗi dòng một phần tử"
            value={defaultValue}
            onChange={(event) => { setDefaultValue(event.target.value); touch('default'); }}
          />
        ) : (
          <Input
            id="variable-default"
            aria-label="Giá trị mặc định"
            type={type === 'number' ? 'number' : 'text'}
            className="font-mono text-sm"
            value={defaultValue}
            onChange={(event) => { setDefaultValue(event.target.value); touch('default'); }}
          />
        )}
        {errorText('default', 'variable-default')}
      </div>

      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>Huỷ</Button>
        <Button type="submit" size="sm" disabled={!valid}>Lưu biến</Button>
      </div>
    </form>
  );
}

function NumberBox({ label, value, onChange, error }: {
  label: string; value?: number; onChange: (text: string) => void; error?: string;
}) {
  return (
    <label className="space-y-1 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <Input
        aria-label={label}
        aria-invalid={Boolean(error)}
        type="number"
        className="h-8 text-sm"
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value)}
      />
      {error ? <span role="alert" className="block text-destructive">{error}</span> : null}
    </label>
  );
}
