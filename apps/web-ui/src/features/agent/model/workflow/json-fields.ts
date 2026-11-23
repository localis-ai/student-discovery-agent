/**
 * A table view of an llm node's JSON output schema. Only flat objects map to rows; anything else (nesting, enum,
 * extra keywords) stays in the JSON editor. Rows write the subset agent_runtime/workflow/nodes/json_check.py checks.
 */

export type JsonFieldType = 'string' | 'number' | 'boolean' | 'string_list' | 'object';

export interface JsonField {
  name: string;
  type: JsonFieldType;
  required: boolean;
  description?: string;
}

export const JSON_FIELD_TYPES: JsonFieldType[] = ['string', 'number', 'boolean', 'string_list', 'object'];
export const JSON_FIELD_NAME = /^[A-Za-z_][A-Za-z0-9_]*$/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function onlyKeys(record: Record<string, unknown>, allowed: readonly string[]): boolean {
  return Object.keys(record).every((key) => allowed.includes(key));
}

function fieldType(schema: unknown): JsonFieldType | null {
  if (!isRecord(schema)) return null;
  if (schema.type === 'array') {
    return onlyKeys(schema, ['type', 'items', 'description']) && isRecord(schema.items)
      && schema.items.type === 'string' && onlyKeys(schema.items, ['type']) ? 'string_list' : null;
  }
  if (!onlyKeys(schema, ['type', 'description'])) return null;
  return schema.type === 'string' || schema.type === 'number' || schema.type === 'boolean' || schema.type === 'object'
    ? schema.type
    : null;
}

export function schemaToFields(schema: unknown): { editable: boolean; fields: JsonField[] } {
  if (schema === undefined || schema === null) return { editable: true, fields: [] };
  if (!isRecord(schema) || schema.type !== 'object' || !onlyKeys(schema, ['type', 'properties', 'required'])) {
    return { editable: false, fields: [] };
  }
  const properties = schema.properties ?? {};
  const required = schema.required ?? [];
  if (!isRecord(properties) || !Array.isArray(required)) return { editable: false, fields: [] };
  // The table only edits what fieldsToSchema writes back unchanged: anything else stays with the JSON editor.
  if (!required.every((name) => typeof name === 'string' && Object.hasOwn(properties, name))) {
    return { editable: false, fields: [] };
  }
  const fields: JsonField[] = [];
  for (const [name, property] of Object.entries(properties)) {
    const type = fieldType(property);
    if (!type) return { editable: false, fields: [] };
    const field: JsonField = { name, type, required: required.includes(name) };
    const description = (property as Record<string, unknown>).description;
    if (typeof description === 'string' && description) field.description = description;
    fields.push(field);
  }
  return { editable: true, fields };
}

export function fieldsToSchema(fields: readonly JsonField[]): Record<string, unknown> {
  const properties: Record<string, unknown> = {};
  for (const field of fields) {
    const base: Record<string, unknown> = field.type === 'string_list'
      ? { type: 'array', items: { type: 'string' } }
      : { type: field.type };
    if (field.description?.trim()) base.description = field.description.trim();
    properties[field.name] = base;
  }
  return { type: 'object', properties, required: fields.filter((field) => field.required).map((field) => field.name) };
}
