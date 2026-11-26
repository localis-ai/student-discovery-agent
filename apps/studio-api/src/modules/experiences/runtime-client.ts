import { z } from 'zod';
import { ProductError } from '@/http/errors';
import type { RequestContext } from '@/http/types';
import {
  callRuntimeAsStudio, classifyRuntimeStatus, readEnvelope, RuntimeCallError, runtimeIssues,
} from '@/infrastructure/runtime/internal-runtime';
import type { PublishReportInput } from '@/modules/experiences/experiences.reports';

export const VALIDATE_TARGET = '/api/v1/internal/experience-validations:run';
export const EVALUATE_TARGET = '/api/v1/internal/experience-evaluations:run';
export const VERIFY_TARGET = '/api/v1/internal/experience-reports:verify';

const TIMEOUT_MS = 5000;
/** Internal runtime boundary rejects bodies over this size (runtime-api.yaml, max_json_bytes). */
export const RUNTIME_MAX_BODY_BYTES = 65536;

export const validationIssueSchema = z.object({
  path: z.string(),
  code: z.string(),
  message: z.string(),
  rule_id: z.string().nullable().optional(),
});

export const validationReportSchema = z.object({
  id: z.string(),
  experience_id: z.string(),
  draft_revision: z.number().int().nonnegative(),
  content_hash: z.string(),
  definition_schema_version: z.string(),
  engine_version: z.string(),
  status: z.enum(['passed', 'failed', 'unsupported']),
  mandatory_passed: z.boolean(),
  issues: z.array(validationIssueSchema),
  created_at: z.string(),
});
export type ValidationReport = z.infer<typeof validationReportSchema>;

export const evaluationCaseResultSchema = z.object({
  case_id: z.string(),
  mandatory: z.boolean(),
  passed: z.boolean(),
  expected: z.record(z.unknown()),
  actual: z.record(z.unknown()),
  issues: z.array(validationIssueSchema),
});

export const evaluationReportSchema = z.object({
  id: z.string(),
  experience_id: z.string(),
  draft_revision: z.number().int().nonnegative(),
  content_hash: z.string(),
  definition_schema_version: z.string(),
  engine_version: z.string(),
  status: z.enum(['passed', 'failed', 'unsupported']),
  mandatory_passed: z.boolean(),
  cases: z.array(evaluationCaseResultSchema),
  created_at: z.string(),
});
export type EvaluationReport = z.infer<typeof evaluationReportSchema>;

export const verifyReportResultSchema = z.object({
  verified: z.boolean(),
  reason: z.string().nullable(),
});
export type VerifyReportResult = z.infer<typeof verifyReportResultSchema>;

export interface ExperienceSnapshotCommandInput {
  experience_id: string;
  definition: Record<string, unknown>;
  expected_revision: number;
  content_hash: string;
  idempotency_key: string;
}

const unavailable = (
  kind: 'dependency_down' | 'timeout' | 'not_configured' | 'misconfigured',
  message = 'Experience validation service is unavailable',
) => new ProductError(503, 'SYS_UNAVAILABLE', message, kind === 'dependency_down' || kind === 'timeout', { kind });

async function callRuntime<T>(
  target: string,
  purpose: string,
  payload: unknown,
  schema: z.ZodType<T>,
  ctx: RequestContext,
): Promise<T> {
  const body = JSON.stringify(payload);
  if (Buffer.byteLength(body, 'utf8') > RUNTIME_MAX_BODY_BYTES) {
    throw new ProductError(
      413,
      'VAL_PAYLOAD_TOO_LARGE',
      `Experience definition exceeds the ${RUNTIME_MAX_BODY_BYTES} byte limit of the runtime`,
    );
  }

  let response: Response;
  try {
    response = await callRuntimeAsStudio({ method: 'POST', target, purpose, body, timeoutMs: TIMEOUT_MS, ctx });
  } catch (error) {
    if (!(error instanceof RuntimeCallError)) throw error;
    if (error.kind === 'not_configured') throw unavailable('not_configured');
    console.error('[experience-runtime] request unreachable', {
      target,
      purpose,
      error: error.causeName,
      requestId: ctx.requestId,
    });
    throw unavailable(error.kind);
  }

  const envelope = await readEnvelope(response);

  if (response.ok && envelope?.success) {
    const parsed = schema.safeParse(envelope.data);
    if (parsed.success) {
      return parsed.data;
    }
    console.error('[experience-runtime] malformed payload from runtime', {
      target,
      issues: parsed.error.issues,
      requestId: ctx.requestId,
    });
    throw unavailable('dependency_down', 'Malformed report received from runtime');
  }

  const runtimeCode = envelope?.error?.code ?? null;
  const issues = runtimeIssues(envelope);
  console.error('[experience-runtime] request failed', {
    target,
    status: response.status,
    runtimeCode,
    issues,
    // 'malformed_body' when the runtime answered with something that is not its JSON envelope.
    kind: envelope === null ? 'malformed_body' : 'runtime_error',
    requestId: ctx.requestId,
  });

  if (response.status === 409) {
    // The runtime exposes CONFLICT_IDEMPOTENCY_KEY on the wire (error_codes.py); the internal name is kept for older runtimes.
    const isCollision = runtimeCode === 'CONFLICT_IDEMPOTENCY_KEY' || runtimeCode === 'IDEMPOTENCY_KEY_COLLISION';
    const code = isCollision ? 'IDEMPOTENCY_KEY_COLLISION' : 'REVISION_CONFLICT';
    throw new ProductError(409, code, envelope?.error?.message ?? 'Runtime reported conflict');
  }
  const failure = classifyRuntimeStatus(response.status);
  if (failure === 'misconfigured') throw unavailable('misconfigured');
  if (failure === 'rejected') {
    // Studio sent a request the runtime refuses: contract drift between the two services, a dependency failure.
    throw new ProductError(502, 'SYS_UNAVAILABLE', 'Runtime rejected experience request', false, {
      kind: 'runtime_rejected',
      runtimeCode,
      issues,
    });
  }
  throw unavailable('dependency_down');
}

export const defaultExperienceRuntimeClient = {
  validate(cmd: ExperienceSnapshotCommandInput, ctx: RequestContext): Promise<ValidationReport> {
    return callRuntime(VALIDATE_TARGET, 'experience.validate', cmd, validationReportSchema, ctx);
  },
  evaluate(cmd: ExperienceSnapshotCommandInput, ctx: RequestContext): Promise<EvaluationReport> {
    return callRuntime(EVALUATE_TARGET, 'experience.evaluate', cmd, evaluationReportSchema, ctx);
  },
  verify(input: PublishReportInput, ctx: RequestContext): Promise<VerifyReportResult> {
    return callRuntime(VERIFY_TARGET, 'experience.verify', input, verifyReportResultSchema, ctx);
  },
};

export type ExperienceRuntimeClient = typeof defaultExperienceRuntimeClient;

let activeClient: ExperienceRuntimeClient = defaultExperienceRuntimeClient;

export function setExperienceRuntimeClient(client: ExperienceRuntimeClient | null): void {
  activeClient = client ?? defaultExperienceRuntimeClient;
}

export function getExperienceRuntimeClient(): ExperienceRuntimeClient {
  return activeClient;
}
