import { ProductError } from '@/http/errors';
import { callRuntimeAsStudio, readEnvelope, RuntimeCallError, type RuntimeFailureKind } from '@/infrastructure/runtime/internal-runtime';

export const RETRIEVAL_TARGET = '/api/v1/internal/knowledge/retrieval';
const TIMEOUT_MS = 3000;

export interface RetrievalPayload {
  knowledge_id: string;
  query: string;
  retrieval_setting: { top_k?: number; score_threshold?: number; semantic_weight?: number; max_chunks_per_doc?: number };
  metadata_condition?: unknown;
}

const unavailable = (kind: string, message = 'Knowledge search is unavailable') =>
  new ProductError(503, 'SYS_UNAVAILABLE', message, kind === 'dependency_down' || kind === 'runtime_starting', { kind });
const INDEX_UNAVAILABLE = 'Knowledge indexing is unavailable';

async function call(
  target: string, purpose: string, body: string, ctx: { requestId: string; traceId: string },
  failed: (kind: RuntimeFailureKind) => ProductError,
): Promise<Response> {
  try {
    return await callRuntimeAsStudio({ method: 'POST', target, purpose, body, timeoutMs: TIMEOUT_MS, ctx });
  } catch (error) {
    if (error instanceof RuntimeCallError) throw failed(error.kind);
    throw error;
  }
}

export async function retrieveKnowledge(
  payload: RetrievalPayload,
  ctx: { requestId: string; traceId: string },
): Promise<{ records: unknown[]; degraded: boolean }> {
  const response = await call(RETRIEVAL_TARGET, 'knowledge.retrieval', JSON.stringify(payload), ctx,
    kind => unavailable(kind === 'not_configured' ? 'not_configured' : 'dependency_down'));
  const envelope = await readEnvelope(response);
  const data = envelope?.data as { records?: unknown[]; degraded?: boolean } | undefined;
  if (response.ok && envelope?.success && Array.isArray(data?.records)) {
    return { records: data.records, degraded: data.degraded === true };
  }
  if (response.status === 404) throw new ProductError(404, 'RES_NOT_FOUND', 'Knowledge base not found');
  if (response.status === 422) throw new ProductError(422, 'VAL_INVALID_INPUT', 'Invalid search request', false, { kind: 'validation', issues: [] });
  console.error('[knowledge] retrieval failed', { status: response.status, requestId: ctx.requestId });
  throw unavailable('dependency_down');
}

export const INDEX_RUNS_TARGET = '/api/v1/internal/knowledge/index-runs';
export type IndexRunStatus = 'started' | 'already_running';

/** Asks the runtime to drain pending revisions. Throws a 503 ProductError when the runtime cannot take the request. */
export async function requestIndexRun(ctx: { requestId: string; traceId: string }): Promise<{ status: IndexRunStatus }> {
  // A sleeping free-tier runtime boots for longer than the kick waits; it drains the queue itself on startup.
  const response = await call(INDEX_RUNS_TARGET, 'knowledge.index', '{}', ctx,
    kind => unavailable(kind === 'timeout' ? 'runtime_starting' : kind, INDEX_UNAVAILABLE));
  const envelope = await readEnvelope(response);
  const status = (envelope?.data as { status?: string } | undefined)?.status;
  if (response.status === 202 && envelope?.success && (status === 'started' || status === 'already_running')) return { status };
  console.error('[knowledge] index run request failed', { status: response.status, requestId: ctx.requestId });
  throw unavailable(response.status === 503 ? 'not_configured' : 'dependency_down', INDEX_UNAVAILABLE);
}
