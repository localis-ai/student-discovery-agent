import { z } from 'zod';
import { ProductError } from '@/http/errors';
import type { RequestContext } from '@/http/types';
import {
  callRuntimeAsStudio, classifyRuntimeStatus, readEnvelope, RuntimeCallError,
} from '@/infrastructure/runtime/internal-runtime';

export const NODE_TYPES_TARGET = '/api/v1/internal/workflow/node-types';
const TIMEOUT_MS = 5_000;

const namespaceVariableSchema = z.object({
  name: z.string(),
  type: z.enum(['string', 'number', 'boolean', 'enum', 'string_list']),
  nullable: z.boolean().optional(),
  description: z.string().optional(),
  values: z.array(z.string()).optional(),
}).strict();

const namespaceSchema = z.object({
  name: z.enum(['sys', 'conv', 'profile', 'result', 'node']),
  title: z.string(),
  access: z.enum(['read_only', 'assign_only']),
  source: z.enum(['static', 'workflow_variables', 'profile_catalog', 'node_output']),
  variables: z.array(namespaceVariableSchema).optional(),
}).strict();

const handleSpecSchema = z.object({
  static: z.array(z.string()),
  from_config: z.object({
    array: z.string(),
    id_field: z.string(),
  }).strict().optional(),
}).strict();

const nodeTypeSchema = z.object({
  type: z.string().min(1),
  title: z.string(),
  description: z.string(),
  config_schema: z.record(z.unknown()),
  handles: handleSpecSchema,
  output_schema: z.record(z.unknown()),
}).strict();

export const workflowNodeTypeCatalogSchema = z.object({
  catalog_version: z.string().min(1),
  namespaces: z.array(namespaceSchema),
  node_types: z.array(nodeTypeSchema).min(1),
}).strict();

export type WorkflowNodeTypeCatalog = z.infer<typeof workflowNodeTypeCatalogSchema>;

type UnavailableKind = 'dependency_down' | 'timeout' | 'not_configured' | 'misconfigured' | 'bad_runtime_response';

const unavailable = (kind: UnavailableKind) =>
  new ProductError(503, 'SYS_UNAVAILABLE', 'Workflow node catalog is unavailable',
    kind === 'dependency_down' || kind === 'timeout', { kind });

/**
 * Fetches the runtime-owned chatflow node-type catalog (DEC-30). Studio forwards it as-is
 * after verifying the contract shape so Studio never keeps a separate node schema.
 */
export async function fetchWorkflowNodeTypes(ctx: RequestContext): Promise<WorkflowNodeTypeCatalog> {
  let response: Response;
  try {
    response = await callRuntimeAsStudio({
      method: 'GET', target: NODE_TYPES_TARGET, purpose: 'agent.validate', body: '', timeoutMs: TIMEOUT_MS, ctx,
      accept: 'application/json',
    });
  } catch (error) {
    if (!(error instanceof RuntimeCallError)) throw error;
    if (error.kind !== 'not_configured') {
      console.error('[agent] runtime node-types unreachable', { error: error.causeName, requestId: ctx.requestId });
    }
    throw unavailable(error.kind);
  }

  const envelope = await readEnvelope(response);

  if (response.ok) {
    if (envelope?.success) {
      const parsed = workflowNodeTypeCatalogSchema.safeParse(envelope.data);
      if (parsed.success) return parsed.data;
      console.error('[agent] runtime node-types returned an unreadable catalog', {
        issues: parsed.error.issues.map(i => `${i.path.join('.')}: ${i.code}`),
        requestId: ctx.requestId,
      });
    } else {
      console.error('[agent] runtime node-types returned an invalid envelope', {
        status: response.status,
        requestId: ctx.requestId,
      });
    }
    throw unavailable('bad_runtime_response');
  }

  console.error('[agent] runtime node-types failed', {
    status: response.status, runtimeCode: envelope?.error?.code ?? null, requestId: ctx.requestId,
  });
  const failure = classifyRuntimeStatus(response.status);
  if (failure === 'misconfigured') throw unavailable('misconfigured');
  if (failure === 'rejected') throw unavailable('bad_runtime_response');
  throw unavailable('dependency_down');
}

type CatalogReader = (ctx: RequestContext) => Promise<WorkflowNodeTypeCatalog>;
let current: CatalogReader = fetchWorkflowNodeTypes;
/** Test seam: tests replace the runtime call; `null` restores the real client. */
export function setNodeTypeCatalogReader(fn: CatalogReader | null): void { current = fn ?? fetchWorkflowNodeTypes; }
export const getNodeTypeCatalog = (): CatalogReader => current;
