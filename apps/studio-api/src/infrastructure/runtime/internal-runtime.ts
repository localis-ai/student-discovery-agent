import { z } from 'zod';
import { getKnowledgeEnv } from '@/config/env';
import { signingKey, signServiceRequest } from '@/infrastructure/runtime/signing';

/**
 * Transport to the agent-runtime internal API: signed headers, timeout, no redirects, and one classification of
 * what went wrong. What a failure means to the caller (message, retryability, domain codes) stays in each module.
 */
export type RuntimeFailureKind = 'not_configured' | 'timeout' | 'dependency_down';

export class RuntimeCallError extends Error {
  constructor(readonly kind: RuntimeFailureKind, readonly causeName: string) {
    super(`runtime call failed: ${kind}`);
    this.name = 'RuntimeCallError';
  }
}

export interface RuntimeRequest {
  method: 'GET' | 'POST';
  target: string;
  body: string;
  timeoutMs: number;
  ctx: { requestId: string; traceId: string };
  accept?: string;
}

export interface WireRequest extends RuntimeRequest {
  baseUrl: string;
  /** Value of `x-internal-caller`. */
  caller: string;
  /** Already signed for this method, target and body. */
  token: string;
}

const isTimeout = (name: string) => name === 'TimeoutError' || name === 'AbortError';

/** Sends one signed request. Throws RuntimeCallError when no response arrived; any HTTP status is returned as is. */
export async function sendToRuntime(req: WireRequest): Promise<Response> {
  try {
    return await fetch(new URL(req.target, req.baseUrl), {
      method: req.method,
      body: req.method === 'POST' ? req.body : undefined,
      redirect: 'error',
      signal: AbortSignal.timeout(req.timeoutMs),
      headers: {
        ...(req.method === 'POST' ? { 'content-type': 'application/json' } : {}),
        ...(req.accept ? { accept: req.accept } : {}),
        'x-internal-caller': req.caller,
        'x-caller-context': req.token,
        'x-request-id': req.ctx.requestId,
        'x-trace-id': req.ctx.traceId,
      },
    });
  } catch (error) {
    // Keep the cause (DNS, refused, redirect, abort) so a 503 can be traced; never the URL or token.
    const name = error instanceof Error ? error.name : 'Error';
    throw new RuntimeCallError(isTimeout(name) ? 'timeout' : 'dependency_down', name);
  }
}

/** Studio -> runtime call signed with the service key for `purpose`. */
export async function callRuntimeAsStudio(req: RuntimeRequest & { purpose: string }): Promise<Response> {
  const env = getKnowledgeEnv();
  const key = signingKey(env.STUDIO_RUNTIME_SIGNING_KEY);
  if (!env.RUNTIME_INTERNAL_URL || !key) throw new RuntimeCallError('not_configured', 'NotConfigured');
  const token = await signServiceRequest(
    req.method, req.target, req.body, key, env.STUDIO_RUNTIME_SIGNING_KID, Date.now(), req.purpose,
  );
  return sendToRuntime({ ...req, baseUrl: env.RUNTIME_INTERNAL_URL, caller: 'sda-studio-api', token });
}

export interface RuntimeEnvelope {
  success: boolean;
  data?: unknown;
  error?: { code?: string; message?: string; details?: unknown };
}

/** The runtime's ApiResponse envelope, or null when the body is not a JSON object (malformed or absent). */
export async function readEnvelope(response: Response): Promise<RuntimeEnvelope | null> {
  const raw = await response.json().catch(() => null) as
    { success?: unknown; data?: unknown; error?: { code?: unknown; message?: unknown; details?: unknown } } | null;
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  const error = raw.error;
  return {
    success: raw.success === true,
    data: raw.data,
    ...(error && typeof error === 'object' ? {
      error: {
        ...(typeof error.code === 'string' ? { code: error.code } : {}),
        ...(typeof error.message === 'string' ? { message: error.message } : {}),
        ...(error.details !== undefined ? { details: error.details } : {}),
      },
    } : {}),
  };
}

export const runtimeIssueSchema = z.object({
  path: z.string(),
  code: z.string(),
  message: z.string(),
  rule_id: z.string().nullable().optional(),
});
export type RuntimeIssue = z.infer<typeof runtimeIssueSchema>;

const runtimeIssuesDetailsSchema = z.object({ issues: z.array(runtimeIssueSchema) });

/** Validation issues the runtime attached as `error.details.issues`; [] when absent or not in that shape. */
export function runtimeIssues(envelope: RuntimeEnvelope | null): RuntimeIssue[] {
  const parsed = runtimeIssuesDetailsSchema.safeParse(envelope?.error?.details);
  return parsed.success ? parsed.data.issues : [];
}

/** 401/403: the runtime rejected studio's key, kid or purpose. Other 4xx: studio sent a request it refuses. */
export function classifyRuntimeStatus(status: number): 'misconfigured' | 'rejected' | 'unavailable' {
  if (status === 401 || status === 403) return 'misconfigured';
  if (status >= 400 && status < 500) return 'rejected';
  return 'unavailable';
}
