import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { SignJWT } from 'jose';
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { dispatch } from '../helpers/api';
import { declaredResponseValidator } from '../helpers/openapi-response';
import { startPostgres, type PostgresHandle } from '../helpers/postgres';
import { call, json } from '../helpers/users-api';
import { migrateProduct } from '@/infrastructure/db/migrate';
import { closeProductDatabase } from '@/infrastructure/db/client';
import { issueAccessToken } from '@/modules/auth/tokens';
import { computeContentHash } from '@/shared/canonical';
import { setPublishReportVerifier } from '@/modules/experiences/experiences.reports';

const DELIVERY_KEY = Buffer.alloc(32, 4);
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
  vi.stubEnv('PRODUCT_DELIVERY_VERIFY_KEY', DELIVERY_KEY.toString('base64'));
  admin = await issueAccessToken('admin', true);
  setPublishReportVerifier({ verify: async () => true });
});

async function runtimeToken(target: string) {
  const now = Math.floor(Date.now() / 1000);
  return new SignJWT({ caller_type: 'runtime_service', purpose: 'release.delivery', method: 'GET', request_target: target,
    body_sha256: createHash('sha256').update('').digest('hex') })
    .setProtectedHeader({ alg: 'HS256', typ: 'sda-internal+jwt', kid: 'runtime' })
    .setIssuer('sda-agent-runtime').setAudience('sda-studio-api').setIssuedAt(now).setExpirationTime(now + 60)
    .sign(new Uint8Array(DELIVERY_KEY));
}

const deliver = async (target: string) => dispatch(new Request(`http://localhost${target}`, {
  headers: { 'x-internal-caller': 'sda-agent-runtime', 'x-caller-context': await runtimeToken(target) } }));

const definition = (version: string) => ({
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
});

let seq = 0;
/** A new experience with one published release; returns both ids. */
async function experienceWithRelease(): Promise<{ expId: string; releaseId: string }> {
  const suffix = `${Date.now()}_${seq++}`;
  const created = await json(await dispatch(call('POST', '/admin/experiences', admin, {
    name: `Delivery ${suffix}`, activity_type: 'personality_assessment', idempotency_key: `create_${suffix}`,
  })));
  const expId = created.data.id as string;
  const content = definition('1.0.0');
  expect((await dispatch(call('PUT', `/admin/experiences/${expId}/draft`, admin, {
    expected_draft_revision: 0, idempotency_key: `draft_${suffix}`, content,
  }))).status).toBe(200);
  const published = await dispatch(call('POST', `/admin/experiences/${expId}/releases`, admin, {
    expected_draft_revision: 1, content_hash: computeContentHash(content), validation_id: 'val_1',
    evaluation_id: 'eval_1', approval_refs: ['appr_qa_pass'], idempotency_key: `pub_${suffix}`,
  }));
  expect(published.status).toBe(201);
  return { expId, releaseId: (await json(published)).data.id as string };
}

const fixture = JSON.parse(readFileSync(new URL('../../../../contracts/fixtures/experience-delivery-descriptor.json', import.meta.url), 'utf8'));
const target = (expId: string, environment = 'demo') =>
  `/api/v1/internal/releases/active?kind=experience&environment=${environment}&experience_id=${expId}`;
const validate = declaredResponseValidator('internal/product-delivery-api.yaml', '/releases/active', 'get', 200);

describe('internal delivery of kind=experience', () => {
  it('hashes the shared fixture like the runtime does', () => {
    expect(computeContentHash(fixture.descriptor.content)).toBe(fixture.descriptor.content_hash);
  });

  it('is 422 RES_EXPERIENCE_NOT_CONFIGURED until a release is active', async () => {
    const { expId } = await experienceWithRelease();
    const res = await deliver(target(expId));
    expect(res.status).toBe(422);
    expect((await res.json()).error.code).toBe('RES_EXPERIENCE_NOT_CONFIGURED');
  });

  it('delivers the active release as a descriptor', async () => {
    const { expId, releaseId } = await experienceWithRelease();
    const activated = await dispatch(call('POST', `/admin/experience-releases/${releaseId}:activate`, admin, {
      environment: 'demo', expected_revision: 0, expected_active_release_id: null, reason: 'test',
      idempotency_key: `deliver_${expId}`,
    }));
    expect(activated.status).toBe(200);
    const res = await deliver(target(expId));
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(validate(body), JSON.stringify(validate.errors)).toBe(true);
    expect(body.data).toMatchObject({
      environment: 'demo', kind: 'experience', release_id: releaseId, delivery_schema_version: 'experience.snapshot.v1',
      definition_schema_version: '1.0', engine_version: '1.0.0', is_demo: false,
    });
    expect(body.data.content_hash).toBe(computeContentHash(body.data.content));
    // The fixture the runtime tests against is a valid descriptor in this same envelope.
    const withFixture = { ...body, data: fixture.descriptor };
    expect(validate(withFixture), JSON.stringify(validate.errors)).toBe(true);
  });

  it('rejects kind=experience without experience_id, and experience_id on kind=agent', async () => {
    expect((await deliver('/api/v1/internal/releases/active?kind=experience&environment=demo')).status).toBe(422);
    expect((await deliver('/api/v1/internal/releases/active?kind=agent&environment=demo&experience_id=x')).status).toBe(422);
  });

  it('delivers only the configured environment', async () => {
    const { expId } = await experienceWithRelease();
    const res = await deliver(target(expId, 'prod'));
    expect(res.status).toBe(422);
    expect((await res.json()).error.code).toBe('VAL_INVALID_REQUEST');
  });
});
