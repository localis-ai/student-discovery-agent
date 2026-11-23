import type { ChatflowVariable, VariableConstraints, VariableType } from '../../types';
import { CHATFLOW_IDENTIFIER_RE } from './edit';

// Mirror of agent_runtime/sessions/schemas/workflow.py (_fits, _within, ConvVariable.consistent): keep in sync.
export const CONSTRAINT_KEYS: Record<VariableType, ReadonlyArray<keyof VariableConstraints>> = {
  string: ['min_length', 'max_length'],
  number: ['minimum', 'maximum', 'integer'],
  boolean: [],
  enum: [],
  string_list: ['max_items', 'item_max_length'],
};
export const MAX_VARIABLE_DESCRIPTION = 300;
export const MAX_ENUM_VALUES = 30;

export function typeFits(type: VariableType, value: unknown, values?: readonly string[]): boolean {
  switch (type) {
    case 'string': return typeof value === 'string';
    case 'number': return typeof value === 'number' && Number.isFinite(value);
    case 'boolean': return typeof value === 'boolean';
    case 'enum': return typeof value === 'string' && (values ?? []).includes(value);
    case 'string_list': return Array.isArray(value) && value.every((item) => typeof item === 'string');
  }
}

/** First broken rule of a value as a short sentence, or null when it fits its type and constraints. */
export function constraintError(
  variable: Pick<ChatflowVariable, 'type' | 'values' | 'constraints'>,
  value: unknown,
): string | null {
  if (!typeFits(variable.type, value, variable.values)) {
    return variable.type === 'enum' ? 'Giá trị không thuộc danh sách cho phép.' : `Giá trị phải có kiểu ${variable.type}.`;
  }
  const limits = variable.constraints ?? {};
  if (typeof value === 'string') {
    if (limits.min_length !== undefined && value.length < limits.min_length) return `Tối thiểu ${limits.min_length} ký tự.`;
    if (limits.max_length !== undefined && value.length > limits.max_length) return `Tối đa ${limits.max_length} ký tự.`;
  } else if (Array.isArray(value)) {
    if (limits.max_items !== undefined && value.length > limits.max_items) return `Tối đa ${limits.max_items} phần tử.`;
    const longest = limits.item_max_length;
    if (longest !== undefined && value.some((item: string) => item.length > longest)) return `Mỗi phần tử tối đa ${longest} ký tự.`;
  } else if (typeof value === 'number') {
    if (limits.integer && !Number.isInteger(value)) return 'Phải là số nguyên.';
    if (limits.minimum !== undefined && value < limits.minimum) return `Tối thiểu ${limits.minimum}.`;
    if (limits.maximum !== undefined && value > limits.maximum) return `Tối đa ${limits.maximum}.`;
  }
  return null;
}

export type DeclarationField = 'name' | 'description' | 'values' | 'default' | `constraints.${keyof VariableConstraints}`;

/** Field-keyed errors of a variable declaration; `others` are the workflow's other variables (for name clashes). */
export function variableDeclarationErrors(
  variable: ChatflowVariable,
  others: readonly ChatflowVariable[],
): Partial<Record<DeclarationField, string>> {
  const errors: Partial<Record<DeclarationField, string>> = {};
  if (!CHATFLOW_IDENTIFIER_RE.test(variable.name)) {
    errors.name = 'Chữ thường, số, gạch dưới; bắt đầu bằng chữ; tối đa 40 ký tự.';
  } else if (others.some((other) => other.name === variable.name)) {
    errors.name = 'Tên biến đã tồn tại.';
  }
  if ((variable.description ?? '').length > MAX_VARIABLE_DESCRIPTION) {
    errors.description = `Tối đa ${MAX_VARIABLE_DESCRIPTION} ký tự.`;
  }
  if (variable.type === 'enum') {
    const values = variable.values ?? [];
    if (!values.length) errors.values = 'Cần ít nhất một giá trị.';
    else if (new Set(values).size !== values.length) errors.values = 'Giá trị bị trùng.';
    else if (values.length > MAX_ENUM_VALUES) errors.values = `Tối đa ${MAX_ENUM_VALUES} giá trị.`;
  }
  const limits = variable.constraints ?? {};
  for (const key of Object.keys(limits) as Array<keyof VariableConstraints>) {
    if (limits[key] !== undefined && !CONSTRAINT_KEYS[variable.type].includes(key)) {
      errors[`constraints.${key}`] = `Ràng buộc này không dùng cho kiểu ${variable.type}.`;
    }
  }
  if (limits.min_length !== undefined && limits.max_length !== undefined && limits.min_length > limits.max_length) {
    errors['constraints.min_length'] = 'Tối thiểu không được lớn hơn tối đa.';
  }
  if (limits.minimum !== undefined && limits.maximum !== undefined && limits.minimum > limits.maximum) {
    errors['constraints.minimum'] = 'Tối thiểu không được lớn hơn tối đa.';
  }
  const defaultError = constraintError(variable, variable.default);
  if (defaultError) errors.default = defaultError;
  return errors;
}
