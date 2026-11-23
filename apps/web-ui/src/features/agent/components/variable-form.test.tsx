import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { VariableForm } from './variable-form';

describe('VariableForm', () => {
  it('declares a constrained number variable', () => {
    const onSave = vi.fn();
    render(<VariableForm others={[]} onSave={onSave} onCancel={() => {}} />);
    fireEvent.change(screen.getByLabelText('Tên biến'), { target: { value: 'score' } });
    fireEvent.change(screen.getByLabelText('Mô tả'), { target: { value: 'Điểm tạm' } });
    fireEvent.click(screen.getByRole('radio', { name: 'number' }));
    fireEvent.change(screen.getByLabelText('Tối thiểu'), { target: { value: '0' } });
    fireEvent.change(screen.getByLabelText('Tối đa'), { target: { value: '10' } });
    fireEvent.click(screen.getByLabelText('Số nguyên'));
    fireEvent.change(screen.getByLabelText('Giá trị mặc định'), { target: { value: '3' } });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu biến' }));
    expect(onSave).toHaveBeenCalledWith({
      name: 'score', description: 'Điểm tạm', type: 'number', default: 3,
      constraints: { minimum: 0, maximum: 10, integer: true },
    });
  });

  it('shows errors next to the fields and keeps Save disabled', () => {
    render(<VariableForm others={[{ name: 'score', type: 'number', default: 0 }]} onSave={() => {}} onCancel={() => {}} />);
    fireEvent.change(screen.getByLabelText('Tên biến'), { target: { value: 'score' } });
    expect(screen.getByText('Tên biến đã tồn tại.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Lưu biến' })).toBeDisabled();
  });

  it('flags a default that breaks the constraints', () => {
    render(<VariableForm others={[]} onSave={() => {}} onCancel={() => {}} />);
    fireEvent.change(screen.getByLabelText('Tên biến'), { target: { value: 'score' } });
    fireEvent.click(screen.getByRole('radio', { name: 'number' }));
    fireEvent.change(screen.getByLabelText('Tối đa'), { target: { value: '10' } });
    fireEvent.change(screen.getByLabelText('Giá trị mặc định'), { target: { value: '42' } });
    expect(screen.getByText('Tối đa 10.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Lưu biến' })).toBeDisabled();
  });

  it('builds enum values and picks the default among them', () => {
    const onSave = vi.fn();
    render(<VariableForm others={[]} onSave={onSave} onCancel={() => {}} />);
    fireEvent.change(screen.getByLabelText('Tên biến'), { target: { value: 'stage' } });
    fireEvent.click(screen.getByRole('radio', { name: 'enum' }));
    for (const value of ['welcome', 'fee']) {
      fireEvent.change(screen.getByLabelText('Thêm giá trị'), { target: { value } });
      fireEvent.keyDown(screen.getByLabelText('Thêm giá trị'), { key: 'Enter' });
    }
    fireEvent.change(screen.getByLabelText('Giá trị mặc định'), { target: { value: 'fee' } });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu biến' }));
    expect(onSave).toHaveBeenCalledWith({ name: 'stage', type: 'enum', values: ['welcome', 'fee'], default: 'fee' });
  });

  it('drops constraints that do not belong to the new type', () => {
    const onSave = vi.fn();
    render(<VariableForm initial={{ name: 's', type: 'string', default: '', constraints: { max_length: 5 } }} others={[]} onSave={onSave} onCancel={() => {}} />);
    fireEvent.click(screen.getByRole('radio', { name: 'boolean' }));
    fireEvent.change(screen.getByLabelText('Giá trị mặc định'), { target: { value: 'false' } });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu biến' }));
    expect(onSave).toHaveBeenCalledWith({ name: 's', type: 'boolean', default: false });
  });
});
