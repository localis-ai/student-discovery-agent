import type { Hono } from 'hono';
import { z } from 'zod';
import { getAgentEnv } from '@/config/env';
import { getProductDatabase } from '@/infrastructure/db/client';
import { ProductError } from '@/http/errors';
import { honoHandler, withHandler } from '@/http/handler';
import { success } from '@/http/response';
import { activeDescriptor } from '@/modules/agent/agent.service';
import { verifyDeliveryRequest } from '@/modules/agent/delivery-auth';

/** The runtime's only read into Product: the release it should run. */
const deliveryQuery = z.object({ kind: z.literal('agent'), environment: z.string().regex(/^[a-z][a-z0-9_-]{0,31}$/) }).strict();

const queryOf = (req: Request) => Object.fromEntries(new URL(req.url).searchParams);

export const handleActiveDelivery = withHandler(async (req, ctx) => {
  await verifyDeliveryRequest(req, '');
  const parsed = deliveryQuery.safeParse(queryOf(req));
  if (!parsed.success) throw new ProductError(422, 'VAL_INVALID_REQUEST', 'Only kind=agent is delivered');
  if (parsed.data.environment !== getAgentEnv().AGENT_DELIVERY_ENVIRONMENT) {
    throw new ProductError(422, 'VAL_INVALID_REQUEST', 'Unknown delivery environment');
  }
  return success(await activeDescriptor(getProductDatabase(), parsed.data.environment), ctx);
});

export function registerDeliveryRoutes(app: Hono): void {
  app.get('/api/v1/internal/releases/active', honoHandler(handleActiveDelivery));
}
