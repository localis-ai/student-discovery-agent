'use client';

import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { MAX_FLOW_EXAMPLES, flowIdProblem } from '../model/workflow/flows';
import type { VariableGroup } from '../model/workflow/variables';
import type { Chatflow, ChatflowFlow } from '../types';
import { NodeField } from './node-fields';

export interface FlowFormValue {
  id: string;
  title: string;
  description: string;
  examples: string[];
  trigger: Record<string, unknown> | null;
  routable: boolean;
  isDefault: boolean;
}

const TRIGGER_PROPERTY = { type: 'object', 'x-widget': 'condition_builder', title: 'Kích hoạt khi' } as const;

/** An empty builder (no rows) is "no trigger", not a condition that never matches. */
function cleanTrigger(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const record = value as Record<string, unknown>;
  const keys = Object.keys(record);
  if (keys.length === 0) return null;
  if (keys.length === 1 && (keys[0] === 'and' || keys[0] === 'or') && Array.isArray(record[keys[0]!]) && (record[keys[0]!] as unknown[]).length === 0) return null;
  return record;
}

/** Profile form of one flow (nghiệp vụ): what the router reads, and when the flow is entered without it. */
export function FlowForm({ chat, flow, variables, onSave, onCancel }: {
  chat: Chatflow;
  /** The flow being edited; absent for a new one. */
  flow?: ChatflowFlow;
  /** Variables a trigger may read (sys, conv, profile, result). */
  variables: VariableGroup[];
  onSave: (value: FlowFormValue) => void;
  onCancel: () => void;
}) {
  const [id, setId] = useState(flow?.id ?? '');
  const [title, setTitle] = useState(flow?.title ?? '');
  const [description, setDescription] = useState(flow?.description ?? '');
  const [examples, setExamples] = useState((flow?.examples ?? []).join('\n'));
  const [trigger, setTrigger] = useState<unknown>(flow?.trigger ?? null);
  const [routable, setRoutable] = useState(flow?.routable !== false);
  const [isDefault, setIsDefault] = useState(flow ? chat.router.default_flow === flow.id : false);
  const [triggerError, setTriggerError] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);

  const exampleList = useMemo(() => examples.split('\n').map(line => line.trim()).filter(Boolean), [examples]);
  const problems = {
    id: flowIdProblem(chat, id, flow?.id),
    title: title.trim() ? (title.length > 100 ? 'Tối đa 100 ký tự.' : null) : 'Cần tiêu đề.',
    description: description.length > 300 ? 'Tối đa 300 ký tự.'
      : routable && !description.trim() ? 'Nghiệp vụ định tuyến được cần mô tả để router chọn.' : null,
    examples: exampleList.length > MAX_FLOW_EXAMPLES ? `Tối đa ${MAX_FLOW_EXAMPLES} câu.`
      : exampleList.some(line => line.length > 200) ? 'Mỗi câu tối đa 200 ký tự.' : null,
    trigger: triggerError,
  };
  const invalid = Object.values(problems).some(Boolean);
  const show = (message: string | null) => (touched && message ? <p role="alert" className="text-xs text-destructive">{message}</p> : null);

  const submit = () => {
    setTouched(true);
    if (invalid) return;
    onSave({
      id, title: title.trim(), description: description.trim(), examples: exampleList, trigger: cleanTrigger(trigger),
      routable, isDefault: routable && isDefault,
    });
  };

  return (
    <form className="space-y-4" onSubmit={event => { event.preventDefault(); submit(); }} noValidate>
      <div className="grid gap-4 sm:grid-cols-[1fr_12rem]">
        <div className="space-y-1.5">
          <Label htmlFor="flow-title">Tiêu đề</Label>
          <Input id="flow-title" value={title} maxLength={100} onChange={event => setTitle(event.target.value)} placeholder="Ví dụ: Tư vấn học phí" />
          {show(problems.title)}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="flow-id">Mã nghiệp vụ</Label>
          <Input id="flow-id" value={id} className="font-mono" onChange={event => setId(event.target.value.trim())} placeholder="hoc_phi" />
          {show(problems.id)}
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="flow-description">Mô tả cho router</Label>
        <Textarea id="flow-description" rows={3} value={description} maxLength={300} onChange={event => setDescription(event.target.value)}
          placeholder="Khi nào học sinh cần nghiệp vụ này? Router đọc mô tả này để chọn." />
        <p className="text-xs text-muted-foreground">{description.length}/300 · Viết theo ý định của học sinh, không phải theo các bước xử lý.</p>
        {show(problems.description)}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="flow-examples">Câu mẫu</Label>
        <Textarea id="flow-examples" rows={4} value={examples} onChange={event => setExamples(event.target.value)}
          placeholder={'học phí ngành CNTT bao nhiêu?\ncó được giảm học phí không'} />
        <p className="text-xs text-muted-foreground">Mỗi dòng một câu, tối đa {MAX_FLOW_EXAMPLES} ({exampleList.length}/{MAX_FLOW_EXAMPLES}).</p>
        {show(problems.examples)}
      </div>

      <div className="flex items-start justify-between gap-4 rounded-md border p-3">
        <div>
          <Label htmlFor="flow-routable">Để router chọn theo mô tả</Label>
          <p className="text-xs text-muted-foreground">Tắt nếu nghiệp vụ chỉ vào qua điều kiện kích hoạt hoặc node Chuyển nghiệp vụ.</p>
        </div>
        <Switch id="flow-routable" checked={routable} onCheckedChange={checked => { setRoutable(checked); if (!checked) setIsDefault(false); }} />
      </div>

      <div className="flex items-start justify-between gap-4 rounded-md border p-3">
        <div>
          <Label htmlFor="flow-default">Nghiệp vụ mặc định</Label>
          <p className="text-xs text-muted-foreground">Chạy khi router không chọn được nghiệp vụ nào (và ở lượt bấm nút không có điều kiện nào khớp).</p>
        </div>
        <Switch id="flow-default" checked={isDefault} disabled={!routable || (flow !== undefined && chat.router.default_flow === flow.id)}
          onCheckedChange={setIsDefault} />
      </div>

      <div className="space-y-1.5 rounded-md border p-3">
        <NodeField name="trigger" property={TRIGGER_PROPERTY} value={trigger} disabled={false} variables={variables}
          onChange={setTrigger} onValidity={(_, error) => setTriggerError(error)} />
        <p className="text-xs text-muted-foreground">Để trống nếu không cần. Khi khớp, lượt chat vào thẳng nghiệp vụ này, trước cả router.</p>
        {show(problems.trigger)}
      </div>

      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onCancel}>Huỷ</Button>
        <Button type="submit">{flow ? 'Lưu nghiệp vụ' : 'Thêm nghiệp vụ'}</Button>
      </div>
    </form>
  );
}
