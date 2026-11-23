import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { NodeDescription } from './node-description';

describe('NodeDescription', () => {
  it('shows one line and opens the full text from "Xem thêm"', () => {
    const long = 'Bắt lượt ngay sau khi học sinh nộp bài Holland, để chuyển sang bước chọn ngành và gợi ý trường.';
    render(<NodeDescription text={long} forceOverflow />);
    expect(screen.getByTestId('node-description')).toHaveTextContent(long);
    fireEvent.click(screen.getByRole('button', { name: 'Xem thêm mô tả' }));
    expect(screen.getByRole('dialog', { name: 'Mô tả node' })).toHaveTextContent(long);
  });

  it('has no button when the text fits', () => {
    render(<NodeDescription text="Ngắn" />);
    expect(screen.queryByRole('button', { name: 'Xem thêm mô tả' })).not.toBeInTheDocument();
  });
});
