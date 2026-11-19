import { readFileSync } from 'node:fs';
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { startPostgres, type PostgresHandle } from '../helpers/postgres';
import { migrateProduct } from '@/infrastructure/db/migrate';
import { closeProductDatabase, getProductDatabase } from '@/infrastructure/db/client';
import { computeContentHash } from '@/shared/canonical';
import { findActiveRelease } from '@/modules/experiences/activation.repository';
import { findExperienceById } from '@/modules/experiences/experiences.repository';
import { seedExperience } from '@/modules/experiences/seed';

const riasec = JSON.parse(readFileSync(
  new URL('../../../../infra/local-releases/experiences/exp_riasec.json', import.meta.url), 'utf8',
)) as Record<string, unknown>;

let pg: PostgresHandle;

beforeAll(async () => {
  pg = await startPostgres();
  await migrateProduct(pg.url);
});

afterAll(async () => {
  try {
    await closeProductDatabase();
  } finally {
    await pg?.stop();
  }
});

beforeEach(() => {
  vi.unstubAllEnvs();
  vi.stubEnv('DATABASE_URL', pg.url);
  vi.stubEnv('SECRET_KEY', 'integration-test-secret');
});

describe('seedExperience', () => {
  it('creates the experience, a release and the demo pointer once', async () => {
    const db = getProductDatabase();
    expect(await seedExperience(db, 'exp_riasec_seed', riasec)).toBe('seeded');
    const active = await findActiveRelease(db, 'exp_riasec_seed', 'demo');
    expect(active?.pointer.revision).toBe(1);
    expect(active?.release).toMatchObject({
      definition_schema_version: '2.0', validation_id: 'seed', evaluation_id: 'seed', published_by: 'seed',
      definition_hash: computeContentHash(riasec),
    });
    expect(await seedExperience(db, 'exp_riasec_seed', riasec)).toBe('skipped');
    expect((await findActiveRelease(db, 'exp_riasec_seed', 'demo'))?.pointer.revision).toBe(1);
  });

  it('adds a new version as a release without moving an existing pointer', async () => {
    const db = getProductDatabase();
    await seedExperience(db, 'exp_seed_versions', riasec);
    const next = { ...riasec, definition_version: '9.9.9' };
    expect(await seedExperience(db, 'exp_seed_versions', next)).toBe('released');
    expect((await findActiveRelease(db, 'exp_seed_versions', 'demo'))?.release.definition_version)
      .toBe(riasec.definition_version);
  });

  it('refuses the same version with different content, and an invalid header, writing nothing', async () => {
    const db = getProductDatabase();
    await seedExperience(db, 'exp_seed_conflict', riasec);
    await expect(seedExperience(db, 'exp_seed_conflict', { ...riasec, is_demo: false })).rejects.toThrow(/different content/);
    await expect(seedExperience(db, 'exp_seed_invalid', { ...riasec, schema_version: '3.0' })).rejects.toThrow();
    expect(await findExperienceById(db, 'exp_seed_invalid')).toBeUndefined();
  });
});
