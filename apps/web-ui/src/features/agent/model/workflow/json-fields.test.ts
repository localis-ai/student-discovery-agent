import { describe, expect, it } from 'vitest';
import { fieldsToSchema, schemaToFields } from './json-fields';

describe('JSON output fields', () => {
  it('reads a flat object schema as editable fields', () => {
    expect(schemaToFields({
      type: 'object',
      properties: {
        stage: { type: 'string', description: 'Giai đoạn' },
        score: { type: 'number' },
        ok: { type: 'boolean' },
        majors: { type: 'array', items: { type: 'string' } },
        meta: { type: 'object' },
      },
      required: ['stage', 'majors'],
    })).toEqual({ editable: true, fields: [
      { name: 'stage', type: 'string', required: true, description: 'Giai đoạn' },
      { name: 'score', type: 'number', required: false },
      { name: 'ok', type: 'boolean', required: false },
      { name: 'majors', type: 'string_list', required: true },
      { name: 'meta', type: 'object', required: false },
    ] });
  });

  it('starts empty without a schema', () => {
    expect(schemaToFields(undefined)).toEqual({ editable: true, fields: [] });
  });

  it('leaves nested or unusual schemas to the JSON editor', () => {
    expect(schemaToFields({ type: 'object', properties: { a: { type: 'object', properties: { b: { type: 'string' } } } } }).editable).toBe(false);
    expect(schemaToFields({ type: 'object', properties: { a: { type: 'string', enum: ['x'] } } }).editable).toBe(false);
    expect(schemaToFields({ type: 'array' }).editable).toBe(false);
  });

  it('writes the subset the runtime checks, and round-trips', () => {
    const fields = [
      { name: 'stage', type: 'string' as const, required: true, description: 'Giai đoạn' },
      { name: 'majors', type: 'string_list' as const, required: false },
    ];
    const schema = fieldsToSchema(fields);
    expect(schema).toEqual({
      type: 'object',
      properties: { stage: { type: 'string', description: 'Giai đoạn' }, majors: { type: 'array', items: { type: 'string' } } },
      required: ['stage'],
    });
    expect(schemaToFields(schema)).toEqual({ editable: true, fields });
  });
});
