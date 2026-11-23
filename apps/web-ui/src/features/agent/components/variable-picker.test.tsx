import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import type { VariableGroup } from '../model/workflow/variables';
import { VariablePicker } from './variable-picker';

const groups: VariableGroup[] = [
  { title: 'Hệ thống', items: [{ path: 'sys.query', type: 'string', description: 'Câu học sinh vừa gõ' },
    { path: 'sys.turn_index', type: 'number' }] },
  { title: 'Biến hội thoại', items: [{ path: 'conv.stage', type: 'enum', values: ['a'] }] },
];

describe('VariablePicker', () => {
  it('lists variables by group with type and description', () => {
    render(<VariablePicker id="v" label="Biến điều kiện 1" value="" groups={groups} disabled={false} onChange={() => {}} />);
    fireEvent.focus(screen.getByLabelText('Biến điều kiện 1'));
    expect(screen.getByRole('group', { name: 'Hệ thống' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /sys\.query.*string.*Câu học sinh vừa gõ/ })).toBeInTheDocument();
  });

  it('filters by what is typed and picks with the keyboard', () => {
    const onChange = vi.fn();
    render(<VariablePicker id="v" label="Biến" value="" groups={groups} disabled={false} onChange={onChange} />);
    const input = screen.getByLabelText('Biến');
    fireEvent.change(input, { target: { value: 'stage' } });
    expect(screen.queryByRole('option', { name: /sys\.query/ })).not.toBeInTheDocument();
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).toHaveBeenLastCalledWith('conv.stage');
  });

  it('accepts a typed path that is not listed', () => {
    const onChange = vi.fn();
    render(<VariablePicker id="v" label="Biến" value="" groups={groups} disabled={false} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText('Biến'), { target: { value: 'profile.grade' } });
    expect(onChange).toHaveBeenLastCalledWith('profile.grade');
    expect(screen.getByRole('option', { name: /Dùng profile\.grade/ })).toBeInTheDocument();
  });

  it('runs the footer action', () => {
    const onSelect = vi.fn();
    render(<VariablePicker id="v" label="Biến" value="" groups={groups} disabled={false} onChange={() => {}}
      footer={{ label: '+ Khai báo biến mới…', onSelect }} />);
    fireEvent.focus(screen.getByLabelText('Biến'));
    fireEvent.click(screen.getByRole('button', { name: '+ Khai báo biến mới…' }));
    expect(onSelect).toHaveBeenCalled();
  });
});
