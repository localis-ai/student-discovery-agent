import type { Hono } from 'hono';
import { z } from 'zod';
import { getAgentEnv } from '@/config/env';
import { getProductDatabase } from '@/infrastructure/db/client';
import { ProductError } from '@/http/errors';
import { honoHandler, withHandler } from '@/http/handler';
import { success } from '@/http/response';
import { activeDescriptor } from '@/modules/agent/agent.service';
import { verifyDeliveryRequest } from '@/modules/agent/delivery-auth';
import { activeExperienceDescriptor } from '@/modules/experiences/activation';
import { resourceIdSchema } from '@/modules/experiences/experiences.schemas';

/** The runtime's only read into Product: the active agent, or the active release of one experience. */
const environment = z.string().regex(/^[a-z][a-z0-9_-]{0,31}$/);
const deliveryQuery = z.discriminatedUnion('kind', [
  z.object({ kind: z.literal('agent'), environment }).strict(),
  z.object({ kind: z.literal('experience'), environment, experience_id: resourceIdSchema }).strict(),
]);

const queryOf = (req: Request) => Object.fromEntries(new URL(req.url).searchParams);

export const handleActiveDelivery = withHandler(async (req, ctx) => {
  await verifyDeliveryRequest(req, '');
  const parsed = deliveryQuery.safeParse(queryOf(req));
  if (!parsed.success) throw new ProductError(422, 'VAL_INVALID_REQUEST', 'Unsupported delivery request');
  const query = parsed.data;
  if (query.environment !== getAgentEnv().AGENT_DELIVERY_ENVIRONMENT) {
    throw new ProductError(422, 'VAL_INVALID_REQUEST', 'Unknown delivery environment');
  }
  const db = getProductDatabase();
  const data = query.kind === 'agent'
    ? await activeDescriptor(db, query.environment)
    : await activeExperienceDescriptor(db, query.experience_id, query.environment);
  return success(data, ctx);
});

export function registerDeliveryRoutes(app: Hono): void {
  app.get('/api/v1/internal/releases/active', honoHandler(handleActiveDelivery));
}
