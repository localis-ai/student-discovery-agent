import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { sql } from 'drizzle-orm';
import { dispatch } from '../helpers/api';
import { declaredResponseValidator } from '../helpers/openapi-response';
import { startPostgres, type PostgresHandle } from '../helpers/postgres';
import { call, json } from '../helpers/users-api';
import { migrateProduct } from '@/infrastructure/db/migrate';
import { closeProductDatabase, getProductDatabase } from '@/infrastructure/db/client';
import { issueAccessToken } from '@/modules/auth/tokens';
import { computeContentHash } from '@/shared/canonical';
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

const FILE = 'public/experience-release-api.yaml';
const activate = (releaseId: string, body: Record<string, unknown>) =>
  dispatch(call('POST', `/admin/experience-releases/${releaseId}:activate`, admin, body));
const rollback = (expId: string, body: Record<string, unknown>) =>
  dispatch(call('POST', `/admin/experiences/${expId}:rollback`, admin, body));
const readActive = (expId: string, environment = 'demo') =>
  dispatch(call('GET', `/admin/experiences/${expId}/active-release?environment=${environment}`, admin));
let key = 0;
const move = (overrides: Record<string, unknown>) => ({
  environment: 'demo', expected_revision: 0, expected_active_release_id: null, reason: 'test',
  idempotency_key: `move_${Date.now()}_${key++}`, ...overrides,
});

describe('Experience active release API', () => {
  it('reads an empty pointer before any activation', async () => {
    const { expId } = await experienceWithReleases([{ version: '1.0.0' }]);
    const res = await readActive(expId);
    const body = await json(res);
    expect(res.status).toBe(200);
    expect(body.data).toMatchObject({ experience_id: expId, environment: 'demo', revision: 0, release_id: null });
    const validate = declaredResponseValidator(FILE, '/admin/experiences/{id}/active-release', 'get', 200);
    expect(validate(body), JSON.stringify(validate.errors)).toBe(true);
  });

  it('activates, then moves the pointer with an audit row in the same transaction', async () => {
    const { expId, releases: [a, b] } = await experienceWithReleases([{ version: '1.0.0' }, { version: '1.1.0' }]);
    const first = await activate(a!, move({}));
    expect(first.status).toBe(200);
    const firstBody = await json(first);
    expect(firstBody.data).toMatchObject({ release_id: a, revision: 1 });
    const validate = declaredResponseValidator(FILE, '/admin/experience-releases/{release_id}:activate', 'post', 200);
    expect(validate(firstBody), JSON.stringify(validate.errors)).toBe(true);
    const second = await activate(b!, move({ expected_revision: 1, expected_active_release_id: a }));
    expect((await json(second)).data).toMatchObject({ release_id: b, revision: 2 });
    expect((await json(await readActive(expId))).data).toMatchObject({ release_id: b, revision: 2 });
    const audit = await getProductDatabase().execute(sql`
      SELECT action, before_ref, after_ref, details FROM product.audit_events
      WHERE target_kind = 'experience' AND target_id = ${expId} ORDER BY at`);
    expect(audit.rows.map(r => [r.action, r.before_ref, r.after_ref])).toEqual([
      ['experience.release.activate', null, a], ['experience.release.activate', a, b],
    ]);
    expect(audit.rows[1]!.details).toMatchObject({ environment: 'demo', reason: 'test', revision: 2 });
  });

  it('rejects a stale revision or a stale expected release with CONFLICT_ACTIVE_RELEASE', async () => {
    const { releases: [a, b] } = await experienceWithReleases([{ version: '1.0.0' }, { version: '1.1.0' }]);
    await activate(a!, move({}));
    const staleRevision = await activate(b!, move({ expected_revision: 0, expected_active_release_id: a }));
    expect(staleRevision.status).toBe(409);
    const staleBody = await json(staleRevision);
    expect(staleBody.error.code).toBe('CONFLICT_ACTIVE_RELEASE');
    expect(staleBody.error.details).toMatchObject({ kind: 'stale_pointer', revision: 1, release_id: a });
    const staleRelease = await activate(b!, move({ expected_revision: 1, expected_active_release_id: null }));
    expect(staleRelease.status).toBe(409);
  });

  it('blocks ABA: a request built on an old revision fails even when the same release is active again', async () => {
    const { expId, releases: [a, b] } = await experienceWithReleases([{ version: '1.0.0' }, { version: '1.1.0' }]);
    await activate(a!, move({}));
    await activate(b!, move({ expected_revision: 1, expected_active_release_id: a }));
    const back = await rollback(expId, move({ target_release_id: a, expected_revision: 2, expected_active_release_id: b }));
    expect(back.status).toBe(200);
    expect((await json(back)).data).toMatchObject({ release_id: a, revision: 3 });
    const old = await activate(b!, move({ expected_revision: 1, expected_active_release_id: a }));
    expect(old.status).toBe(409);
  });

  it('answers no_changes when the target is already active', async () => {
    const { releases: [a] } = await experienceWithReleases([{ version: '1.0.0' }]);
    await activate(a!, move({}));
    const again = await activate(a!, move({ expected_revision: 1, expected_active_release_id: a }));
    expect(again.status).toBe(409);
    expect((await json(again)).error.details).toMatchObject({ kind: 'no_changes' });
  });

  it('keeps demo releases and unapproved releases out of prod', async () => {
    const { releases: [demo, unapproved, approved] } = await experienceWithReleases([
      { version: '1.0.0', is_demo: true }, { version: '1.1.0', approval_refs: [] }, { version: '1.2.0' },
    ]);
    const demoRes = await activate(demo!, move({ environment: 'prod' }));
    expect(demoRes.status).toBe(422);
    expect((await json(demoRes)).error).toMatchObject({ code: 'VAL_INCOMPATIBLE_RELEASE', details: { kind: 'demo_in_production' } });
    const unapprovedRes = await activate(unapproved!, move({ environment: 'prod' }));
    expect((await json(unapprovedRes)).error.details).toMatchObject({ kind: 'approval_required' });
    expect((await activate(approved!, move({ environment: 'prod' }))).status).toBe(200);
    expect((await activate(demo!, move({ environment: 'demo' }))).status).toBe(200);
  });

  it('rejects unknown environments, unknown releases and rollback targets from another experience', async () => {
    const { expId, releases: [a] } = await experienceWithReleases([{ version: '1.0.0' }]);
    const { releases: [foreign] } = await experienceWithReleases([{ version: '1.0.0' }]);
    expect((await json(await activate(a!, move({ environment: 'staging' })))).error.code).toBe('VAL_INVALID_INPUT');
    expect((await readActive(expId, 'staging')).status).toBe(422);
    expect((await activate('exp_rel_0000000000000000', move({}))).status).toBe(404);
    expect((await rollback(expId, move({ target_release_id: foreign }))).status).toBe(404);
    expect((await readActive('exp_missing')).status).toBe(404);
  });

  it('replays the same request and rejects a reused key with another payload', async () => {
    const { releases: [a, b] } = await experienceWithReleases([{ version: '1.0.0' }, { version: '1.1.0' }]);
    const body = move({});
    const first = await json(await activate(a!, body));
    const replay = await json(await activate(a!, body));
    expect(replay.data).toEqual(first.data);
    const collision = await activate(b!, { ...body });
    expect(collision.status).toBe(409);
    expect((await json(collision)).error.code).toBe('CONFLICT_IDEMPOTENCY_KEY');
  });
});
