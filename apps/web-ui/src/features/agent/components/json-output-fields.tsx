'use client';

import { Plus, Trash2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Input } from '@/components/ui/input';
import { canonical } from '../model/config';
import { fieldsToSchema, JSON_FIELD_NAME, JSON_FIELD_TYPES, schemaToFields, type JsonField } from '../model/workflow/json-fields';

function rowErrors(rows: readonly JsonField[]): Array<string | null> {
  return rows.map((row, index) => {
    if (!JSON_FIELD_NAME.test(row.name)) return 'Tên chỉ gồm chữ, số, gạch dưới; không bắt đầu bằng số.';
    if (rows.findIndex((other) => other.name === row.name) !== index) return 'Tên trường bị trùng.';
    return null;
  });
}

/**
 * Output fields of a JSON llm node as a table (name, type, required, description). It writes `json_schema` only
 * while every row is valid; nested schemas stay in the JSON editor under "Nâng cao".
 */
export function JsonOutputFields({ value, disabled, onChange }: {
  value: unknown; disabled: boolean; onChange: (schema: Record<string, unknown>) => void;
}) {
  const parsed = schemaToFields(value);
  const [rows, setRows] = useState<JsonField[]>(parsed.fields);
  const lastEmitted = useRef(canonical(value));
  useEffect(() => {
    const next = canonical(value);
    if (next !== lastEmitted.current) {
      lastEmitted.current = next;
      setRows(schemaToFields(value).fields);
    }
  }, [value]);

  if (!parsed.editable) {
    return (
      <div role="group" aria-label="Trường đầu ra JSON" className="space-y-1">
        <span className="text-sm font-medium">Trường đầu ra JSON</span>
        <p className="text-xs text-muted-foreground">Schema có cấu trúc lồng nhau hoặc enum: sửa ở mục JSON schema trong phần Nâng cao.</p>
      </div>
    );
  }

  const errors = rowErrors(rows);
  const update = (next: JsonField[]) => {
    setRows(next);
    if (rowErrors(next).every((error) => error === null)) {
      const schema = fieldsToSchema(next);
      lastEmitted.current = canonical(schema);
      onChange(schema);
    }
  };
  const setRow = (index: number, patch: Partial<JsonField>) => update(rows.map((row, at) => (at === index ? { ...row, ...patch } : row)));

  return (
    <div role="group" aria-label="Trường đầu ra JSON" className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Trường đầu ra JSON</span>
        <span className="text-xs text-muted-foreground">{rows.length} trường</span>
      </div>
      {rows.map((row, index) => (
        <div key={index} className="space-y-1.5 rounded-lg border bg-muted/30 p-2">
          <div className="flex items-center gap-1.5">
            <Input
              aria-label={`Tên trường ${index + 1}`}
              aria-invalid={Boolean(errors[index])}
              className="h-8 min-w-0 flex-1 font-mono text-xs"
              value={row.name}
              disabled={disabled}
              onChange={(event) => setRow(index, { name: event.target.value.trim() })}
            />
            <select
              aria-label={`Kiểu trường ${index + 1}`}
              className="h-8 w-28 shrink-0 rounded-md border border-input bg-background px-2 font-mono text-xs"
              value={row.type}
              disabled={disabled}
              onChange={(event) => setRow(index, { type: event.target.value as JsonField['type'] })}
            >
              {JSON_FIELD_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
            <button
              type="button"
              aria-label={`Xoá trường ${index + 1}`}
              className="rounded p-1.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive disabled:opacity-50"
              disabled={disabled}
              onClick={() => update(rows.filter((_, at) => at !== index))}
            >
              <Trash2 className="size-3.5" />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <Input
              aria-label={`Mô tả trường ${index + 1}`}
              placeholder="Mô tả cho LLM (tùy chọn)"
              className="h-8 min-w-0 flex-1 text-xs"
              value={row.description ?? ''}
              disabled={disabled}
              onChange={(event) => setRow(index, { description: event.target.value || undefined })}
            />
            <label className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground">
              <input
                type="checkbox"
                aria-label={`Bắt buộc trường ${index + 1}`}
                checked={row.required}
                disabled={disabled}
                onChange={(event) => setRow(index, { required: event.target.checked })}
              />
              Bắt buộc
            </label>
          </div>
          {errors[index] ? <p role="alert" className="text-xs text-destructive">{errors[index]}</p> : null}
        </div>
      ))}
      <button
        type="button"
        className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed py-2 text-sm text-muted-foreground hover:border-primary/50 hover:text-primary disabled:pointer-events-none disabled:opacity-50"
        disabled={disabled}
        onClick={() => update([...rows, { name: `field_${rows.length + 1}`, type: 'string', required: true }])}
      >
        <Plus className="size-4" /> Thêm trường
      </button>
      <p className="text-xs text-muted-foreground">Node sau đọc bằng <code>‹id node›.json.‹tên trường›</code>.</p>
    </div>
  );
}
