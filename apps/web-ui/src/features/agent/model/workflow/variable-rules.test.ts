import { describe, expect, it } from 'vitest';
import type { ChatflowVariable } from '../../types';
import { constraintError, typeFits, variableDeclarationErrors } from './variable-rules';

const score: ChatflowVariable = { name: 'score', type: 'number', default: 0, constraints: { minimum: 0, maximum: 10, integer: true } };

describe('variable rules (mirror of agent_runtime value_fits)', () => {
  it('checks the type first', () => {
    expect(typeFits('number', 1)).toBe(true);
    expect(typeFits('number', true)).toBe(false);
    expect(typeFits('enum', 'a', ['a'])).toBe(true);
    expect(typeFits('enum', 'b', ['a'])).toBe(false);
    expect(typeFits('string_list', ['a', 1])).toBe(false);
  });

  it('explains which constraint a value breaks', () => {
    expect(constraintError(score, 5)).toBeNull();
    expect(constraintError(score, 11)).toBe('Tối đa 10.');
    expect(constraintError(score, -1)).toBe('Tối thiểu 0.');
    expect(constraintError(score, 2.5)).toBe('Phải là số nguyên.');
    expect(constraintError({ type: 'string', constraints: { max_length: 3 } }, 'abcd')).toBe('Tối đa 3 ký tự.');
    expect(constraintError({ type: 'string', constraints: { min_length: 2 } }, 'a')).toBe('Tối thiểu 2 ký tự.');
    expect(constraintError({ type: 'string_list', constraints: { max_items: 1 } }, ['a', 'b'])).toBe('Tối đa 1 phần tử.');
    expect(constraintError({ type: 'string_list', constraints: { item_max_length: 1 } }, ['ab'])).toBe('Mỗi phần tử tối đa 1 ký tự.');
    expect(constraintError({ type: 'number' }, 'x')).toBe('Giá trị phải có kiểu number.');
    expect(constraintError({ type: 'enum', values: ['a'] }, 'b')).toBe('Giá trị không thuộc danh sách cho phép.');
  });

  it('validates a declaration like the runtime does', () => {
    expect(variableDeclarationErrors(score, [])).toEqual({});
    expect(variableDeclarationErrors({ ...score, name: '1bad' }, []).name).toMatch(/Chữ thường/);
    expect(variableDeclarationErrors(score, [{ ...score }]).name).toBe('Tên biến đã tồn tại.');
    expect(variableDeclarationErrors({ ...score, constraints: { minimum: 5, maximum: 1 } }, [])['constraints.minimum'])
      .toBe('Tối thiểu không được lớn hơn tối đa.');
    expect(variableDeclarationErrors({ ...score, constraints: { max_length: 3 } }, [])['constraints.max_length'])
      .toBe('Ràng buộc này không dùng cho kiểu number.');
    expect(variableDeclarationErrors({ ...score, default: 20 }, []).default).toBe('Tối đa 10.');
    expect(variableDeclarationErrors({ name: 'e', type: 'enum', values: [], default: '' }, []).values)
      .toBe('Cần ít nhất một giá trị.');
    expect(variableDeclarationErrors({ name: 'e', type: 'enum', values: ['a', 'a'], default: 'a' }, []).values)
      .toBe('Giá trị bị trùng.');
    expect(variableDeclarationErrors({ ...score, description: 'x'.repeat(301) }, []).description).toBe('Tối đa 300 ký tự.');
  });
});
