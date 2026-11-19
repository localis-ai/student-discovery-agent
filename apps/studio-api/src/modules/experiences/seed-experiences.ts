import { readdir, readFile } from 'node:fs/promises';
import { basename, join } from 'node:path';
import { closeProductDatabase, getProductDatabase } from '@/infrastructure/db/client';
import { redact } from '@/infrastructure/db/migrate';
import { seedExperience } from '@/modules/experiences/seed';

const DEFAULT_DIR = '../../infra/local-releases/experiences';

/** Usage: DATABASE_URL=... pnpm db:seed-experiences [dir]. One experience per <experience_id>.json; idempotent. */
async function main(): Promise<void> {
  const dir = process.argv[2] ?? DEFAULT_DIR;
  const url = process.env.DATABASE_URL;
  if (!url) {
    console.error('db:seed-experiences: usage: DATABASE_URL=... pnpm db:seed-experiences [dir]');
    process.exitCode = 1;
    return;
  }
  try {
    const files = (await readdir(dir)).filter(name => name.endsWith('.json')).sort();
    if (files.length === 0) throw new Error(`no *.json in ${dir}`);
    for (const file of files) {
      const content = JSON.parse(await readFile(join(dir, file), 'utf8'));
      if (!content || typeof content !== 'object' || Array.isArray(content)) throw new Error(`${file} must be an object`);
      const id = basename(file, '.json');
      console.log(`db:seed-experiences: ${id}: ${await seedExperience(getProductDatabase(), id, content)}`);
    }
  } catch (error) {
    console.error(`db:seed-experiences: failed: ${redact(error instanceof Error ? error.message : String(error), url)}`);
    process.exitCode = 1;
  } finally {
    await closeProductDatabase();
  }
}

void main();
