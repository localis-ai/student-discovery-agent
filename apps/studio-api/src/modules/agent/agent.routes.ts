import type { Hono } from 'hono';
import { getProductDatabase } from '@/infrastructure/db/client';
import { honoHandler, withHandler } from '@/http/handler';
import { success } from '@/http/response';
import { requireAdmin } from '@/modules/auth/auth.service';
import { readStrictJsonBody } from '@/http/json-body';
import { ProductError } from '@/http/errors';
import { paginationSchema, publishSchema, releaseIdSchema, restoreSchema, saveDraftSchema } from '@/modules/agent/agent.schemas';
import { DEBUG_BODY, debugRunIdSchema, debugRunRequestSchema, readDebugRun, runDebugRun, streamDebugRun } from '@/modules/agent/debug-runs';
import { getNodeTypeCatalog } from '@/modules/agent/node-types';
import {
  getActiveAgent, getAgentRelease, listAgentAudit, listAgentReleases, publish, readDraft, restore, saveDraftContent, validateDraft,
} from '@/modules/agent/agent.service';

const ADMIN = '/api/v1/admin/agent';
// 60 KB: the draft is forwarded to the runtime's 64 KB internal boundary wrapped as {"content": …}.
const BODY = { maxBytes: 60 * 1024 };

export const handleReadDraft = withHandler(async (req, ctx) => {
  await requireAdmin(req);
  return success(await readDraft(getProductDatabase()), ctx);
});

export const handleSaveDraft = withHandler(async (req, ctx) => {
  const admin = await requireAdmin(req);
  const body = saveDraftSchema.parse(await readStrictJsonBody(req, BODY));
  return success(await saveDraftContent(getProductDatabase(), body, admin.sub), ctx);
});

export const handleValidateDraft = withHandler(async (req, ctx) => {
  await requireAdmin(req);
  return success(await validateDraft(getProductDatabase(), ctx), ctx);
});

export const handleCreateDebugRun = withHandler(async (req, ctx) => {
  const admin = await requireAdmin(req);
  const body = debugRunRequestSchema.parse(await readStrictJsonBody(req, DEBUG_BODY));
  const db = getProductDatabase();
  if ((req.headers.get('accept') ?? '').includes('text/event-stream')) return streamDebugRun(db, body, admin.sub, ctx);
  return success(await runDebugRun(db, body, admin.sub, ctx), ctx);
});

export const handleReadDebugRun = withHandler<{ run: string }>(async (req, ctx, route) => {
  await requireAdmin(req);
  const id = debugRunIdSchema.safeParse(route.params.run);
  if (!id.success) throw new ProductError(404, 'RES_NOT_FOUND', 'Debug run not found');
  return success(await readDebugRun(getProductDatabase(), id.data), ctx);
});

export const handleReadNodeTypes = withHandler(async (req, ctx) => {
  await requireAdmin(req);
  return success(await getNodeTypeCatalog()(ctx), ctx);
});

const queryOf = (req: Request) => Object.fromEntries(new URL(req.url).searchParams);
const pageMeta = (limit: number, next_cursor: string | null) => ({ meta: { pagination: { limit, next_cursor, has_more: next_cursor !== null } } });

export const handlePublish = withHandler(async (req, ctx) => {
  const admin = await requireAdmin(req);
  const body = publishSchema.parse(await readStrictJsonBody(req));
  const res = await publish(getProductDatabase(), body, admin.sub, ctx);
  return success(res.data, ctx, res.status);
});

// Hono cannot express `/:id:restore`; the param captures the suffix and is split here.
export const handleReleaseAction = withHandler<{ release: string }>(async (req, ctx, route) => {
  const admin = await requireAdmin(req);
  const match = /^(agr_[0-9a-f]{24}):restore$/.exec(route.params.release);
  if (!match) throw new ProductError(404, 'RES_NOT_FOUND', 'Not found');
  const body = restoreSchema.parse(await readStrictJsonBody(req));
  const res = await restore(getProductDatabase(), match[1]!, body, admin.sub, ctx);
  return success(res.data, ctx, res.status);
});

export const handleListReleases = withHandler(async (req, ctx) => {
  await requireAdmin(req);
  const query = paginationSchema.parse(queryOf(req));
  const { items, next_cursor } = await listAgentReleases(getProductDatabase(), query);
  return success({ items }, ctx, 200, pageMeta(query.limit, next_cursor));
});

export const handleReadRelease = withHandler<{ release: string }>(async (req, ctx, route) => {
  await requireAdmin(req);
  return success(await getAgentRelease(getProductDatabase(), releaseIdSchema.parse(route.params.release)), ctx);
});

export const handleReadActive = withHandler(async (req, ctx) => {
  await requireAdmin(req);
  return success(await getActiveAgent(getProductDatabase()), ctx);
});

export const handleListAudit = withHandler(async (req, ctx) => {
  await requireAdmin(req);
  const query = paginationSchema.parse(queryOf(req));
  const { items, next_cursor } = await listAgentAudit(getProductDatabase(), query);
  return success({ items }, ctx, 200, pageMeta(query.limit, next_cursor));
});

export function registerAgentRoutes(app: Hono): void {
  app.get(`${ADMIN}/draft`, honoHandler(handleReadDraft));
  app.put(`${ADMIN}/draft`, honoHandler(handleSaveDraft));
  app.post(`${ADMIN}/draft/validations`, honoHandler(handleValidateDraft));
  app.post(`${ADMIN}/draft/debug-runs`, honoHandler(handleCreateDebugRun));
  app.get(`${ADMIN}/debug-runs/:run`, honoHandler(handleReadDebugRun));
  app.get(`${ADMIN}/workflow/node-types`, honoHandler(handleReadNodeTypes));
  app.post(`${ADMIN}/releases`, honoHandler(handlePublish));
  app.get(`${ADMIN}/releases`, honoHandler(handleListReleases));
  app.get(`${ADMIN}/releases/:release`, honoHandler(handleReadRelease));
  app.post(`${ADMIN}/releases/:release`, honoHandler(handleReleaseAction));
  app.get(`${ADMIN}/active`, honoHandler(handleReadActive));
  app.get(`${ADMIN}/audit-logs`, honoHandler(handleListAudit));
}
