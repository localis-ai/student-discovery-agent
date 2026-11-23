import type { ChatflowNode } from '../../types';
import { conditionLines } from './condition';

const MAX_LINES = 3;

/** What a canvas card shows under its title: code stays code, names replace ids where Studio knows them. */
export interface CardSummary {
  lines: Array<{ text: string; code: boolean }>;
  chips: string[];
  /** Set when the node cannot run yet (a required setting is missing). */
  warning?: string;
}

export interface SummaryContext {
  knowledgeBaseName?: (id: string) => string | undefined;
  toolLabel?: (name: string) => string | undefined;
}

function text(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.replace(/\s+/g, ' ').trim() : undefined;
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

function count(value: unknown): number {
  return Array.isArray(value) ? value.length : 0;
}

function valueText(value: unknown): string {
  return typeof value === 'string' ? `"${value}"` : JSON.stringify(value ?? null);
}

function assignmentLine(raw: unknown): string | undefined {
  if (!raw || typeof raw !== 'object') return undefined;
  const { variable, operation = 'set', value } = raw as Record<string, unknown>;
  if (typeof variable !== 'string') return undefined;
  if (operation === 'clear') return `xoá ${variable}`;
  if (operation === 'append' || operation === 'add') return `${variable} += ${valueText(value)}`;
  return `${variable} = ${valueText(value)}`;
}

const code = (value: string) => ({ text: value, code: true });
const plain = (value: string) => ({ text: value, code: false });

/** What a node does, for its canvas card; empty lines and chips when there is nothing to show. */
export function nodeSummary(node: ChatflowNode, context: SummaryContext = {}): CardSummary {
  const config = node.config ?? {};
  const summary: CardSummary = { lines: [], chips: [] };
  switch (node.type) {
    case 'if_else': {
      const lines = conditionLines(config.condition, MAX_LINES);
      summary.lines = lines.map(code);
      if (!lines.length) summary.warning = 'Chưa có điều kiện';
      break;
    }
    case 'intent_classifier': {
      summary.lines = [code(text(config.input) ?? '{{sys.query}}')];
      const labels = count(config.labels);
      if (labels) summary.chips.push(`${labels} nhãn`);
      else summary.warning = 'Chưa có nhãn';
      break;
    }
    case 'llm': {
      const prompt = text(config.prompt);
      if (prompt) summary.lines = [plain(prompt)];
      else summary.warning = 'Chưa có prompt';
      if (config.output === 'json') summary.chips.push('JSON');
      break;
    }
    case 'agent': {
      const tools = strings(config.tools);
      const instructions = text(config.instructions);
      if (tools.length) summary.lines.push(plain(tools.map((name) => context.toolLabel?.(name) ?? name).join(', ')));
      else summary.chips.push('Chưa chọn tool');
      if (instructions) summary.lines.push(plain(instructions));
      break;
    }
    case 'knowledge_retrieval': {
      const id = text(config.knowledge_base_id);
      if (id) {
        const name = context.knowledgeBaseName?.(id);
        summary.lines.push(name ? plain(name) : code(id));
      } else {
        summary.warning = 'Chưa chọn KB';
      }
      const query = text(config.query);
      if (query) summary.lines.push(code(query));
      break;
    }
    case 'tool': {
      const tool = text(config.tool);
      if (tool) {
        const label = context.toolLabel?.(tool);
        summary.lines = [label ? plain(label) : code(tool)];
      } else {
        summary.warning = 'Chưa chọn tool';
      }
      break;
    }
    case 'profile_propose': {
      const fields = strings(config.fields);
      if (fields.length) summary.lines = [code(fields.join(', '))];
      break;
    }
    case 'assign': {
      const lines = (Array.isArray(config.assignments) ? config.assignments.map(assignmentLine) : [])
        .filter((line): line is string => Boolean(line));
      const shown = lines.length > MAX_LINES ? [...lines.slice(0, MAX_LINES), `+${lines.length - MAX_LINES} phép gán`] : lines;
      summary.lines = shown.map(code);
      break;
    }
    case 'answer': {
      const body = text(config.text);
      const blocks = count(config.blocks);
      if (body) summary.lines = [plain(body)];
      if (blocks) summary.chips.push(`+${blocks} block`);
      if (!body && !blocks) summary.warning = 'Chưa có nội dung';
      break;
    }
  }
  return summary;
}

/** Text rows a card reserves for its summary: each line wraps to at most 2 rows; chips and warning share one. */
export function summaryHeightLines(summary: CardSummary): number {
  return summary.lines.length * 2 + (summary.chips.length || summary.warning ? 1 : 0);
}
