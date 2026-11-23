import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { JsonOutputFields } from './json-output-fields';

describe('JsonOutputFields', () => {
  it('edits a flat schema as rows', () => {
    const onChange = vi.fn();
    render(<JsonOutputFields value={{ type: 'object', properties: { stage: { type: 'string' } }, required: ['stage'] }} disabled={false} onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: 'Thêm trường' }));
    fireEvent.change(screen.getByLabelText('Tên trường 2'), { target: { value: 'majors' } });
    fireEvent.change(screen.getByLabelText('Kiểu trường 2'), { target: { value: 'string_list' } });
    fireEvent.click(screen.getByLabelText('Bắt buộc trường 2'));
    expect(onChange).toHaveBeenLastCalledWith({
      type: 'object',
      properties: { stage: { type: 'string' }, majors: { type: 'array', items: { type: 'string' } } },
      required: ['stage'],
    });
  });

  it('does not write while a name is invalid or duplicated', () => {
    const onChange = vi.fn();
    render(<JsonOutputFields value={{ type: 'object', properties: { a: { type: 'string' } }, required: [] }} disabled={false} onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: 'Thêm trường' }));
    onChange.mockClear();
    fireEvent.change(screen.getByLabelText('Tên trường 2'), { target: { value: 'a' } });
    expect(screen.getByText('Tên trường bị trùng.')).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });

  it('sends nested schemas to the JSON editor', () => {
    render(<JsonOutputFields value={{ type: 'object', properties: { a: { type: 'object', properties: {} } } }} disabled={false} onChange={() => {}} />);
    expect(screen.getByText(/sửa ở mục JSON schema trong phần Nâng cao/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Thêm trường' })).not.toBeInTheDocument();
  });
});
