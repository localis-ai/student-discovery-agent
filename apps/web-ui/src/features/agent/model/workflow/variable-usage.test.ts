import { describe, expect, it } from 'vitest';
import type { AgentConfig, ChatflowWorkflow } from '../../types';
import { enumValueUsage, removeVariable, renameVariable, upsertVariable, variableUsage } from './variable-usage';

const workflow: ChatflowWorkflow = {
  entry: 'start',
  variables: [{ name: 'stage', type: 'enum', values: ['a', 'b'], default: 'a' }, { name: 'stager', type: 'string', default: '' }],
  nodes: [
    { id: 'start', type: 'start' },
    { id: 'check', type: 'if_else', config: { condition: { '==': [{ var: 'conv.stage' }, 'b'] } } },
    { id: 'set', type: 'assign', config: { assignments: [{ variable: 'conv.stage', value: 'b' }] } },
    { id: 'say', type: 'answer', config: { text: 'Bạn ở {{ conv.stage }} và {{conv.stager}}' } },
    { id: 'miss', type: 'if_else', config: { condition: { missing: ['conv.stager'] } } },
  ],
  edges: [],
};

describe('variable usage', () => {
  it('finds every node that reads or writes a variable, and nothing that merely shares a prefix', () => {
    expect(variableUsage(workflow, 'stage')).toEqual(['check', 'set', 'say']);
    expect(variableUsage(workflow, 'stager')).toEqual(['say', 'miss']);
  });

  it('finds where an enum value is compared or assigned', () => {
    expect(enumValueUsage(workflow, 'stage', 'b')).toEqual(['check', 'set']);
    expect(enumValueUsage(workflow, 'stage', 'a')).toEqual([]);
  });

  it('renames the declaration, every reference and persona case conv keys', () => {
    const config: AgentConfig = {
      workflow,
      persona_cases: [{
        id: 'p', title: 'P', initial_state: { conv: { stage: 'a', other: 1 } },
        turns: [{ input: { text: 'x' }, expect: { conv: { stage: 'b' } } }],
      }],
    };
    const next = renameVariable(config, 'stage', 'journey');
    const renamed = next.workflow as ChatflowWorkflow;
    expect(renamed.variables!.map((variable) => variable.name)).toEqual(['journey', 'stager']);
    expect(variableUsage(renamed, 'journey')).toEqual(['check', 'set', 'say']);
    expect(variableUsage(renamed, 'stage')).toEqual([]);
    expect((renamed.nodes[3]!.config as { text: string }).text).toBe('Bạn ở {{conv.journey}} và {{conv.stager}}');
    const persona = (next.persona_cases as Array<{ initial_state: { conv: object }; turns: Array<{ expect: { conv: object } }> }>)[0]!;
    expect(persona.initial_state.conv).toEqual({ journey: 'a', other: 1 });
    expect(persona.turns[0]!.expect.conv).toEqual({ journey: 'b' });
  });

  it('adds, replaces and removes declarations', () => {
    const added = upsertVariable(workflow, { name: 'score', type: 'number', default: 0 });
    expect(added.variables!.at(-1)!.name).toBe('score');
    const edited = upsertVariable(added, { name: 'score', type: 'number', default: 1, description: 'Điểm' }, 'score');
    expect(edited.variables!.find((variable) => variable.name === 'score')).toMatchObject({ default: 1, description: 'Điểm' });
    expect(edited.variables).toHaveLength(3);
    expect(removeVariable(edited, 'score').variables!.some((variable) => variable.name === 'score')).toBe(false);
    expect(() => removeVariable(workflow, 'stage')).toThrow(/đang dùng/);
  });
});
