import { requireAdmin } from '@/modules/auth/auth.service';
import { getProductDatabase } from '@/infrastructure/db/client';
import { readStrictJsonBody } from '@/http/json-body';
import { withHandler } from '@/http/handler';
import { success } from '@/http/response';
import { bulkUpdateSchema } from '@/modules/users/users.schemas';
import { bulkUpdateUsers } from '@/modules/users/users.service';


export const handlePut = withHandler(async (req, ctx) => {
  await requireAdmin(req);
  const { users } = bulkUpdateSchema.parse(await readStrictJsonBody(req));
  const { data, summary, ...rest } = await bulkUpdateUsers(getProductDatabase(), users, ctx);
  return success(data, ctx, 200, { ...rest, meta: { summary } });
});
