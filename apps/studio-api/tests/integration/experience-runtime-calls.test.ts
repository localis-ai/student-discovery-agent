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
import { setExperienceRuntimeClient, type ExperienceRuntimeClient } from '@/modules/experiences/runtime-client';

let pg: PostgresHandle;
let admin: string;

beforeAll(async () => {
  pg = await startPostgres();
  await migrateProduct(pg.url);
});

afterAll(async () => {
  setPublishReportVerifier(null);
  setExperienceRuntimeClient(null);
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
  setPublishReportVerifier({ verify: async () => true });
});

const definition = {
  schema_version: '1.0',
  definition_id: 'personality_assessment_mvp',
  definition_version: '1.0.0',
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
};

async function experienceWithDraft(suffix: string): Promise<{ id: string; hash: string }> {
  const created = await json(await dispatch(call('POST', '/admin/experiences', admin, {
    name: `Exp ${suffix}`, activity_type: 'personality_assessment', idempotency_key: `create_${suffix}`,
  })));
  const id = created.data.id as string;
  const saved = await dispatch(call('PUT', `/admin/experiences/${id}/draft`, admin, {
    expected_draft_revision: 0, idempotency_key: `draft_${suffix}`, content: definition,
  }));
  expect(saved.status).toBe(200);
  return { id, hash: computeContentHash(definition) };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(r => { resolve = r; });
  return { promise, resolve };
}

const report = (id: string, experienceId: string, hash: string) => ({
  id, experience_id: experienceId, draft_revision: 1, content_hash: hash, definition_schema_version: '1.0',
  engine_version: '1.0.0', status: 'passed' as const, mandatory_passed: true, issues: [], cases: [],
  created_at: new Date().toISOString(),
});

/** True when nobody holds the advisory lock of (scope, key): the lock is taken and released in a throwaway transaction. */
async function lockIsFree(scope: string, key: string): Promise<boolean> {
  return getProductDatabase().transaction(async tx => {
    const result = await tx.execute(sql`SELECT pg_try_advisory_xact_lock(hashtextextended(${`${scope}|${key}`}, 0)) AS free`);
    return result.rows[0]!.free === true;
  });
}

const reportsOf = async (id: string) =>
  (await getProductDatabase().execute(sql`SELECT id, kind FROM product.experience_reports WHERE experience_id = ${id}`)).rows;

/** Resolves once `fn` has been called, so a test can act while the runtime call is still pending. */
const called = (fn: ReturnType<typeof vi.fn>) => vi.waitFor(() => expect(fn).toHaveBeenCalled());

describe('experience runtime calls stay outside the transaction', () => {
  it('validate: the idempotency lock is free and the draft is editable while the runtime is still answering', async () => {
    const { id, hash } = await experienceWithDraft('val_lock');
    const gate = deferred<ReturnType<typeof report>>();
    const validate = vi.fn(() => gate.promise);
    setExperienceRuntimeClient({ validate, evaluate: vi.fn(), verify: vi.fn() } as unknown as ExperienceRuntimeClient);

    const pending = dispatch(call('POST', `/admin/experiences/${id}/validations`, admin, {
      expected_revision: 1, content_hash: hash, idempotency_key: 'val-lock-1',
    }));
    await called(validate);

    expect(await lockIsFree(`validate:${id}`, 'val-lock-1')).toBe(true);
    const edit = await dispatch(call('PUT', `/admin/experiences/${id}/draft`, admin, {
      expected_draft_revision: 1, idempotency_key: 'draft_val_lock_2', content: { ...definition, definition_version: '1.0.1' },
    }));
    expect(edit.status).toBe(200);

    gate.resolve(report('val_lock_1', id, hash));
    const response = await pending;
    // The report describes a draft that no longer exists: it must not be stored.
    expect(response.status).toBe(409);
    expect((await json(response)).error.code).toBe('CONFLICT_REVISION');
    expect(await reportsOf(id)).toEqual([]);
  });

  it('evaluate: stores the report once and replays the same key without calling the runtime again', async () => {
    const { id, hash } = await experienceWithDraft('eval_replay');
    const evaluate = vi.fn(async () => report('eval_replay_1', id, hash));
    setExperienceRuntimeClient({ validate: vi.fn(), evaluate, verify: vi.fn() } as unknown as ExperienceRuntimeClient);
    const body = { expected_revision: 1, content_hash: hash, idempotency_key: 'eval-replay-1' };

    const first = await dispatch(call('POST', `/admin/experiences/${id}/evaluations`, admin, body));
    expect(first.status).toBe(201);
    const second = await dispatch(call('POST', `/admin/experiences/${id}/evaluations`, admin, body));
    expect(second.status).toBe(201);
    expect((await json(second)).data.id).toBe('eval_replay_1');
    expect(evaluate).toHaveBeenCalledTimes(1);
    expect(await reportsOf(id)).toEqual([{ id: 'eval_replay_1', kind: 'evaluation' }]);
  });

  it('validate: concurrent requests with one key store one report and answer alike', async () => {
    const { id, hash } = await experienceWithDraft('val_race');
    const validate = vi.fn(async () => report('val_race_1', id, hash));
    setExperienceRuntimeClient({ validate, evaluate: vi.fn(), verify: vi.fn() } as unknown as ExperienceRuntimeClient);
    const body = { expected_revision: 1, content_hash: hash, idempotency_key: 'val-race-1' };

    const responses = await Promise.all([
      dispatch(call('POST', `/admin/experiences/${id}/validations`, admin, body)),
      dispatch(call('POST', `/admin/experiences/${id}/validations`, admin, body)),
    ]);
    expect(responses.map(r => r.status)).toEqual([201, 201]);
    const [a, b] = await Promise.all(responses.map(r => json(r)));
    expect(a.data).toEqual(b.data);
    expect(await reportsOf(id)).toHaveLength(1);
  });

  it('publish: the idempotency lock is free while the reports are being verified; a draft edited meanwhile is refused', async () => {
    const { id, hash } = await experienceWithDraft('pub_lock');
    const gate = deferred<boolean>();
    const verify = vi.fn(() => gate.promise);
    setPublishReportVerifier({ verify });

    const pending = dispatch(call('POST', `/admin/experiences/${id}/releases`, admin, {
      expected_draft_revision: 1, content_hash: hash, validation_id: 'v', evaluation_id: 'e',
      approval_refs: ['appr_qa_pass'], idempotency_key: 'pub-lock-1',
    }));
    await called(verify);

    expect(await lockIsFree(`publish:${id}`, 'pub-lock-1')).toBe(true);
    const edit = await dispatch(call('PUT', `/admin/experiences/${id}/draft`, admin, {
      expected_draft_revision: 1, idempotency_key: 'draft_pub_lock_2', content: { ...definition, definition_version: '1.0.1' },
    }));
    expect(edit.status).toBe(200);

    gate.resolve(true);
    const response = await pending;
    expect(response.status).toBe(409);
    const releases = await json(await dispatch(call('GET', `/admin/experiences/${id}/releases`, admin)));
    expect(releases.data.items).toEqual([]);
  });
});
