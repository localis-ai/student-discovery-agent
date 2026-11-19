import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { sql } from 'drizzle-orm';
import { dispatch } from '../helpers/api';
import { startPostgres, type PostgresHandle } from '../helpers/postgres';
import { call, json } from '../helpers/users-api';
import { migrateProduct } from '@/infrastructure/db/migrate';
import { closeProductDatabase, getProductDatabase } from '@/infrastructure/db/client';
import { issueAccessToken } from '@/modules/auth/tokens';
import { computeContentHash } from '@/modules/experiences/canonical';
import { setPublishReportVerifier } from '@/modules/experiences/experiences.reports';
import { findActiveRelease, findPointer, lockPointerKey, upsertPointer } from '@/modules/experiences/activation.repository';

let pg: PostgresHandle;
let admin: string;

beforeAll(async () => {
  pg = await startPostgres();
  await migrateProduct(pg.url);
});

afterAll(async () => {
  setPublishReportVerifier(null);
  try {
    await closeProductDatabase();
  } finally {
    await pg?.stop();
  }
});

beforeEach(async () => {
  vi.unstubAllEnvs();
  vi.stubEnv('DATABASE_URL', pg.url);
  vi.stubEnv('SECRET_KEY', 'integration-test-secret');
  admin = await issueAccessToken('admin', true);
  // No report service runs here; publishing only needs an accepting verifier.
  setPublishReportVerifier({ verify: async () => true });
});

const definition = (version: string, overrides: Record<string, unknown> = {}) => ({
  schema_version: '1.0',
  definition_id: 'personality_assessment_mvp',
  definition_version: version,
  engine_version: '1.0.0',
  is_demo: false,
  questions: [1, 2, 3, 4, 5, 6].map(n => ({ question_id: `q${n}`, text: `Question ${n}` })),
  houses: [1, 2, 3, 4, 5, 6].map(n => ({ house_id: `h${n}`, name: `House ${n}` })),
  selection_rules: { type: 'all' },
  scoring_rules: { type: 'sum' },
  coverage_rules: { type: 'complete' },
  tie_policy: { type: 'random' },
  templates: { result: 'Result template' },
  evaluation_cases: [],
  approval_refs: ['appr_qa_pass'],
  ...overrides,
});

let seq = 0;
/** A new experience with one published release per entry of `versions`; returns release ids in publish order. */
async function experienceWithReleases(
  versions: Array<{ version: string; is_demo?: boolean; approval_refs?: string[] }>,
): Promise<{ expId: string; releases: string[] }> {
  const suffix = `${Date.now()}_${seq++}`;
  const created = await json(await dispatch(call('POST', '/admin/experiences', admin, {
    name: `Activation ${suffix}`, activity_type: 'personality_assessment', idempotency_key: `create_${suffix}`,
  })));
  const expId = created.data.id as string;
  const releases: string[] = [];
  let revision = 0;
  for (const [index, entry] of versions.entries()) {
    const content = definition(entry.version, { is_demo: entry.is_demo ?? false });
    const saved = await dispatch(call('PUT', `/admin/experiences/${expId}/draft`, admin, {
      expected_draft_revision: revision, idempotency_key: `draft_${suffix}_${index}`, content,
    }));
    expect(saved.status).toBe(200);
    revision += 1;
    const published = await dispatch(call('POST', `/admin/experiences/${expId}/releases`, admin, {
      expected_draft_revision: revision, content_hash: computeContentHash(content), validation_id: 'val_1',
      evaluation_id: 'eval_1', approval_refs: entry.approval_refs ?? ['appr_qa_pass'], idempotency_key: `pub_${suffix}_${index}`,
    }));
    expect(published.status).toBe(201);
    releases.push((await json(published)).data.id as string);
  }
  return { expId, releases };
}

describe('activation repository', () => {
  it('upserts one pointer per (experience, environment) and joins its release', async () => {
    const { expId, releases } = await experienceWithReleases([{ version: '1.0.0' }, { version: '1.1.0' }]);
    const db = getProductDatabase();
    expect(await findPointer(db, expId, 'demo')).toBeUndefined();
    await db.transaction(async tx => {
      await lockPointerKey(tx, expId, 'demo');
      await upsertPointer(tx, { experience_id: expId, environment: 'demo', release_id: releases[0]!, revision: 1, updated_by: 'admin' });
    });
    await db.transaction(tx => upsertPointer(tx, {
      experience_id: expId, environment: 'demo', release_id: releases[1]!, revision: 2, updated_by: 'admin',
    }));
    const active = await findActiveRelease(db, expId, 'demo');
    expect(active?.pointer).toMatchObject({ release_id: releases[1], revision: 2 });
    expect(active?.release.definition_version).toBe('1.1.0');
    expect(await findPointer(db, expId, 'prod')).toBeUndefined();
  });

  it('rejects environments outside demo and prod at the database', async () => {
    const { expId, releases } = await experienceWithReleases([{ version: '1.0.0' }]);
    await expect(getProductDatabase().execute(sql`
      INSERT INTO product.experience_active (experience_id, environment, release_id, revision, updated_by)
      VALUES (${expId}, 'staging', ${releases[0]!}, 1, 'admin')`)).rejects.toThrow();
  });
});
