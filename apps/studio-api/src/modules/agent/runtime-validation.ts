import { z } from 'zod';
import { ProductError } from '@/http/errors';
import type { RequestContext } from '@/http/types';
import {
  callRuntimeAsStudio, classifyRuntimeStatus, readEnvelope, RuntimeCallError,
} from '@/infrastructure/runtime/internal-runtime';

export const VALIDATE_TARGET = '/api/v1/internal/agent-snapshots:validate';
// A persona gate can run a few hundred stubbed turns, so validation gets more room than a lookup.
const TIMEOUT_MS = 15000;

const personaReportSchema = z.object({
  cases: z.array(z.object({
    id: z.string(), title: z.string(), mandatory: z.boolean(), passed: z.boolean(),
    mismatches: z.array(z.object({ path: z.string(), message: z.string() })),
  })),
});
const reportSchema = z.object({
  valid: z.boolean(),
  content_hash: z.string(),
  issues: z.array(z.object({ path: z.string(), code: z.string(), message: z.string() })),
  persona_report: personaReportSchema.nullish(),
  // false: a graph-only check, so `valid` does not say the persona gate passed. Absent means the runtime predates it.
  personas_checked: z.boolean().optional(),
});
export type AgentValidation = z.infer<typeof reportSchema>;
export type AgentIssue = AgentValidation['issues'][number];

// Only a transient outage is retryable; a rejected key or a malformed request will fail the same way again.
const unavailable = (kind: 'dependency_down' | 'timeout' | 'not_configured' | 'misconfigured') =>
  new ProductError(503, 'SYS_UNAVAILABLE', 'Agent validation is unavailable', kind === 'dependency_down' || kind === 'timeout', { kind });

/** The runtime owns agent schema rules; anything short of a well-formed report is a failure, never a pass. */
export async function validateWithRuntime(
  content: Record<string, unknown>, ctx: RequestContext, options: { personas?: boolean } = {},
): Promise<AgentValidation> {
  const body = JSON.stringify(options.personas === false ? { content, personas: false } : { content });
  let response: Response;
  try {
    response = await callRuntimeAsStudio({
      method: 'POST', target: VALIDATE_TARGET, purpose: 'agent.validate', body, timeoutMs: TIMEOUT_MS, ctx,
    });
  } catch (error) {
    if (!(error instanceof RuntimeCallError)) throw error;
    if (error.kind !== 'not_configured') {
      console.error('[agent] runtime validation unreachable', { error: error.causeName, requestId: ctx.requestId });
    }
    throw unavailable(error.kind);
  }
  const envelope = await readEnvelope(response);
  const parsed = response.ok && envelope?.success ? reportSchema.safeParse(envelope.data) : null;
  if (parsed?.success) return parsed.data;
  console.error('[agent] runtime validation failed', {
    status: response.status, runtimeCode: envelope?.error?.code ?? null, requestId: ctx.requestId,
  });
  const failure = classifyRuntimeStatus(response.status);
  if (failure === 'misconfigured') throw unavailable('misconfigured');
  if (failure === 'rejected') {
    throw new ProductError(500, 'SYS_INTERNAL_ERROR', 'Agent validation request was rejected', false, { kind: 'runtime_rejected' });
  }
  throw unavailable('dependency_down');
}

type Validator = typeof validateWithRuntime;
let current: Validator = validateWithRuntime;
/** Test seam: integration tests replace the runtime call; `null` restores the real client. */
export function setAgentValidator(fn: Validator | null): void { current = fn ?? validateWithRuntime; }
export const getAgentValidator = (): Validator => current;
