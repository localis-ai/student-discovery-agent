import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import type { VariableGroup } from '../model/workflow/variables';
import { NodeField, type SchemaProperty } from './node-fields';

const DEFAULT_GROUPS: VariableGroup[] = [
  { title: 'Hệ thống', items: [{ path: 'sys.query', type: 'string' }, { path: 'sys.turn_index', type: 'number' }] },
];

function Stateful({ name, property, initial, onValue, variables = DEFAULT_GROUPS }: {
  name: string; property: SchemaProperty; initial?: unknown; onValue: (value: unknown) => void; variables?: VariableGroup[];
}) {
  const [value, setValue] = useState(initial);
  return (
    <NodeField
      name={name}
      property={property}
      value={value}
      disabled={false}
      variables={variables}
      onChange={(next) => { setValue(next); onValue(next); }}
      onValidity={() => {}}
    />
  );
}

const ASSIGNMENTS: SchemaProperty = {
  type: 'array',
  items: {
    type: 'object',
    required: ['variable'],
    properties: {
      variable: { type: 'string', pattern: '^conv\\.[a-z][a-z0-9_]*$' },
      operation: { type: 'string', enum: ['set', 'append', 'clear', 'add'], default: 'set' },
      value: {},
    },
  },
};
const CONV_GROUPS: VariableGroup[] = [
  { title: 'Hệ thống', items: [{ path: 'sys.query', type: 'string' }] },
  { title: 'Biến hội thoại', items: [
    { path: 'conv.stage', type: 'enum', values: ['welcome', 'fee'] },
    { path: 'conv.score', type: 'number', constraints: { minimum: 0, maximum: 10 } },
  ] },
];

describe('NodeField', () => {
  it('picks only conv variables for an assignment and offers enum values', () => {
    const onValue = vi.fn();
    render(<Stateful name="assignments" property={ASSIGNMENTS} initial={[{ variable: 'conv.stage', operation: 'set' }]}
      onValue={onValue} variables={CONV_GROUPS} />);
    fireEvent.focus(screen.getByLabelText('Biến'));
    expect(screen.queryByRole('option', { name: /sys\.query/ })).not.toBeInTheDocument();
    expect(screen.getByRole('option', { name: /conv\.score/ })).toBeInTheDocument();
    const value = screen.getByLabelText('Giá trị');
    expect(value.tagName).toBe('SELECT');
    fireEvent.change(value, { target: { value: 'fee' } });
    expect(onValue).toHaveBeenLastCalledWith([{ variable: 'conv.stage', operation: 'set', value: 'fee' }]);
  });

  it('flags a number that breaks the declared range right under the field', () => {
    const onValue = vi.fn();
    render(<Stateful name="assignments" property={ASSIGNMENTS} initial={[{ variable: 'conv.score', operation: 'set', value: 1 }]}
      onValue={onValue} variables={CONV_GROUPS} />);
    fireEvent.change(screen.getByLabelText('Giá trị'), { target: { value: '42' } });
    expect(onValue).toHaveBeenLastCalledWith([{ variable: 'conv.score', operation: 'set', value: 42 }]);
    expect(screen.getByText('Tối đa 10.')).toBeInTheDocument();
  });

  it('keeps the free value box for templates and for add/append', () => {
    render(<Stateful name="assignments" property={ASSIGNMENTS} initial={[{ variable: 'conv.score', operation: 'add', value: 1 }]}
      onValue={() => {}} variables={CONV_GROUPS} />);
    expect(screen.getByLabelText('Giá trị').getAttribute('type')).not.toBe('number');
  });

  it('offers the values of a fixed-value variable and only the comparisons of its type', () => {
    const onValue = vi.fn();
    render(<Stateful name="condition" property={{ type: 'object', 'x-widget': 'condition_builder' }} onValue={onValue}
      variables={[{ title: 'Hệ thống', items: [{ path: 'sys.interaction_outcome', type: 'string', values: ['none', 'assessment_completed'] }] }]} />);
    fireEvent.click(screen.getByRole('button', { name: 'Thêm điều kiện' }));
    fireEvent.change(screen.getByLabelText('Biến điều kiện 1'), { target: { value: 'sys.interaction_outcome' } });
    const operators = [...(screen.getByLabelText('Phép so sánh 1') as HTMLSelectElement).options].map((option) => option.value);
    expect(operators).toEqual(['==', '!=', 'in', 'missing']);
    const valueBox = screen.getByLabelText('Giá trị so sánh 1');
    expect(valueBox.tagName).toBe('SELECT');
    fireEvent.change(valueBox, { target: { value: 'assessment_completed' } });
    expect(onValue).toHaveBeenLastCalledWith({ '==': [{ var: 'sys.interaction_outcome' }, 'assessment_completed'] });
  });

  it('builds an if_else condition from rows', () => {
    const onValue = vi.fn();
    render(<Stateful name="condition" property={{ type: 'object', 'x-widget': 'condition_builder' }} onValue={onValue} />);
    fireEvent.click(screen.getByRole('button', { name: 'Thêm điều kiện' }));
    fireEvent.change(screen.getByLabelText('Biến điều kiện 1'), { target: { value: 'sys.turn_index' } });
    fireEvent.change(screen.getByLabelText('Phép so sánh 1'), { target: { value: '>=' } });
    fireEvent.change(screen.getByLabelText('Giá trị so sánh 1'), { target: { value: '3' } });
    expect(onValue).toHaveBeenLastCalledWith({ '>=': [{ var: 'sys.turn_index' }, 3] });

    fireEvent.click(screen.getByRole('button', { name: 'Thêm điều kiện' }));
    fireEvent.change(screen.getByLabelText('Biến điều kiện 2'), { target: { value: 'conv.step' } });
    fireEvent.change(screen.getByLabelText('Phép so sánh 2'), { target: { value: 'missing' } });
    fireEvent.change(screen.getByLabelText('Cách kết hợp điều kiện'), { target: { value: 'or' } });
    expect(onValue).toHaveBeenLastCalledWith({ or: [{ '>=': [{ var: 'sys.turn_index' }, 3] }, { missing: ['conv.step'] }] });
    expect(screen.queryByLabelText('Giá trị so sánh 2')).not.toBeInTheDocument();
  });

  it('switches a simple condition to JSON and back', () => {
    render(<Stateful name="condition" property={{ type: 'object', 'x-widget': 'condition_builder' }}
      initial={{ '==': [{ var: 'sys.query' }, 'hi'] }} onValue={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: 'Chế độ nâng cao (JSON)' }));
    expect(screen.getByLabelText('Điều kiện')).toHaveValue(JSON.stringify({ '==': [{ var: 'sys.query' }, 'hi'] }, null, 2));
    fireEvent.click(screen.getByRole('button', { name: 'Dùng trình tạo điều kiện' }));
    expect(screen.getByLabelText('Giá trị so sánh 1')).toHaveValue('hi');
  });

  it('edits a list of objects from its item schema, within maxItems', () => {
    const onValue = vi.fn();
    const property = {
      type: 'array', maxItems: 2,
      items: { type: 'object', required: ['id', 'description'], properties: {
        id: { type: 'string' }, description: { type: 'string' }, examples: { type: 'array', items: { type: 'string' }, default: [] },
      } },
    };
    render(<Stateful name="labels" property={property} initial={[]} onValue={onValue} />);
    fireEvent.click(screen.getByRole('button', { name: 'Thêm nhãn' }));
    expect(onValue).toHaveBeenLastCalledWith([{ id: '', description: '', examples: [] }]);
    fireEvent.change(screen.getByLabelText('Mã nhánh'), { target: { value: 'tu_van' } });
    fireEvent.change(screen.getByLabelText('Câu ví dụ'), { target: { value: 'tư vấn ngành\n\nhọc gì' } });
    expect(onValue).toHaveBeenLastCalledWith([{ id: 'tu_van', description: '', examples: ['tư vấn ngành', 'học gì'] }]);
    fireEvent.click(screen.getByRole('button', { name: 'Thêm nhãn' }));
    expect(screen.getByRole('button', { name: 'Thêm nhãn' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Xoá nhãn 1' }));
    expect(onValue).toHaveBeenLastCalledWith([{ id: '', description: '', examples: [] }]);
  });

  it('keeps an enum value of the schema type', () => {
    const onValue = vi.fn();
    render(<Stateful name="level" property={{ enum: [1, 2] }} onValue={onValue} />);
    fireEvent.change(screen.getByRole('combobox', { name: 'level' }), { target: { value: '2' } });
    expect(onValue).toHaveBeenLastCalledWith(2);
  });

  it('reads an optional number and an untyped value', () => {
    const onValue = vi.fn();
    const { unmount } = render(<Stateful name="max_tool_steps" property={{ anyOf: [{ type: 'integer', maximum: 8 }, { type: 'null' }], default: null }} onValue={onValue} />);
    fireEvent.change(screen.getByLabelText('Số bước tool tối đa'), { target: { value: '4' } });
    expect(onValue).toHaveBeenLastCalledWith(4);
    unmount();

    render(<Stateful name="value" property={{ default: null }} onValue={onValue} />);
    const input = screen.getByLabelText('Giá trị');
    fireEvent.change(input, { target: { value: 'done' } });
    expect(onValue).toHaveBeenLastCalledWith('done');
    fireEvent.change(input, { target: { value: '"7"' } });
    expect(onValue).toHaveBeenLastCalledWith('7');
    expect(input).toHaveValue('"7"');
  });

  it('inserts a variable into a template field at the caret', () => {
    const onValue = vi.fn();
    render(<Stateful name="prompt" property={{ type: 'string' }} initial="Hỏi: " onValue={onValue} />);
    const prompt = screen.getByLabelText('Prompt') as HTMLTextAreaElement;
    prompt.setSelectionRange(5, 5);
    fireEvent.change(screen.getByLabelText('Chèn biến vào Prompt'), { target: { value: 'sys.query' } });
    expect(onValue).toHaveBeenLastCalledWith('Hỏi: {{sys.query}}');
  });
});

describe('goto_flow target', () => {
  it('lists the other flows by title and stores the chosen id', async () => {
    const { FlowsContext } = await import('./flows-context');
    const onValue = vi.fn();
    render(
      <FlowsContext.Provider value={{ currentFlowId: 'main', flows: [{ id: 'main', title: 'Chính' }, { id: 'fee', title: 'Học phí' }] }}>
        <Stateful name="flow" property={{ type: 'string' }} onValue={onValue} />
      </FlowsContext.Provider>,
    );
    const select = screen.getByLabelText('Nghiệp vụ đích');
    expect(screen.queryByRole('option', { name: /Chính/ })).not.toBeInTheDocument();
    fireEvent.change(select, { target: { value: 'fee' } });
    expect(onValue).toHaveBeenLastCalledWith('fee');
  });
});
