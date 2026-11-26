import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { JSON_FIELD_NAME, schemaToFields } from './json-fields';
import { CHATFLOW_IDENTIFIER_RE, CHATFLOW_LIMITS, CONSTRAINT_BOUNDS, placeholderPaths, RESERVED_FLOW_IDS, RESERVED_NODE_IDS } from './rules';

// Read from contracts/ directly (not the gen:api copy) so a stale copy cannot hide drift. The runtime runs the same
// fixture in tests/unit/workflow/test_chatflow_rules_parity.py.
const fixture = JSON.parse(readFileSync(resolve(__dirname, '../../../../../../../contracts/fixtures/chatflow-rules.json'), 'utf8')) as {
  identifier_pattern: string;
  reserved_node_ids: string[];
  reserved_flow_ids: string[];
  limits: Record<string, number>;
  variable_constraint_bounds: Record<string, { minimum: number; maximum: number }>;
  placeholder_cases: Array<{ text: string; paths: string[] }>;
};

describe('chatflow rules parity with contracts/fixtures/chatflow-rules.json', () => {
  it('uses the contract limits, ids and identifier grammar', () => {
    expect(CHATFLOW_LIMITS).toEqual(fixture.limits);
    expect(CONSTRAINT_BOUNDS).toEqual(fixture.variable_constraint_bounds);
    expect(CHATFLOW_IDENTIFIER_RE.source).toBe(fixture.identifier_pattern);
    expect([...RESERVED_NODE_IDS].sort()).toEqual([...fixture.reserved_node_ids].sort());
    expect([...RESERVED_FLOW_IDS].sort()).toEqual([...fixture.reserved_flow_ids].sort());
  });

  it.each(fixture.placeholder_cases)('reads the placeholders of $text like the runtime', ({ text, paths }) => {
    expect(placeholderPaths(text)).toEqual(paths);
  });

  it('only accepts JSON output field names a placeholder can reach', () => {
    for (const name of ['major_name', 'score2']) {
      expect(JSON_FIELD_NAME.test(name)).toBe(true);
      expect(placeholderPaths(`{{ask.json.${name}}}`)).toEqual([`ask.json.${name}`]);
    }
    for (const name of ['majorName', '_private', '2nd']) {
      expect(JSON_FIELD_NAME.test(name)).toBe(false);
      expect(placeholderPaths(`{{ask.json.${name}}}`)).toEqual([]);
    }
    // A stored schema keeps loading; the table flags the name instead of dropping the field.
    expect(schemaToFields({ type: 'object', properties: { majorName: { type: 'string' } } }).fields).toHaveLength(1);
  });
});
