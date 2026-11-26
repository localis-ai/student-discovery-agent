import { and, desc, eq, sql } from 'drizzle-orm';
import type { ProductExecutor } from '@/infrastructure/db/client';
import {
  experienceDrafts,
  experienceReleases,
  experienceReports,
  experiences,
} from '@/infrastructure/db/schema';
import { computeContentHash } from '@/shared/canonical';
import {
  decodeExperienceCursor, decodeReleaseCursor, encodeExperienceCursor, encodeReleaseCursor,
} from '@/modules/experiences/experiences.cursor';


export type ExperienceRow = typeof experiences.$inferSelect;
export type ExperienceDraftRow = typeof experienceDrafts.$inferSelect;
export type ExperienceReleaseRow = typeof experienceReleases.$inferSelect;
export type ExperienceReportRow = typeof experienceReports.$inferSelect;


/** Microsecond-precision UTC text for a timestamptz column, used as the keyset cursor value. */
function cursorTimestamp(column: typeof experiences.created_at | typeof experienceReleases.published_at) {
  return sql<string>`to_char(${column} AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')`;
}

export async function findExperienceById(
  db: ProductExecutor,
  id: string,
): Promise<ExperienceRow | undefined> {
  const [row] = await db.select().from(experiences).where(eq(experiences.id, id)).limit(1);
  return row;
}

export async function findExperienceWithDraft(
  db: ProductExecutor,
  id: string,
): Promise<{ experience: ExperienceRow; draft: ExperienceDraftRow | null } | undefined> {
  const [row] = await db
    .select({
      experience: experiences,
      draft: experienceDrafts,
    })
    .from(experiences)
    .leftJoin(experienceDrafts, eq(experiences.id, experienceDrafts.experience_id))
    .where(eq(experiences.id, id))
    .limit(1);

  if (!row) return undefined;
  return {
    experience: row.experience,
    draft: row.draft?.draft_id ? row.draft : null,
  };
}

export async function listExperiences(
  db: ProductExecutor,
  opts: { limit: number; cursor?: string },
): Promise<{
  items: Array<{
    experience: ExperienceRow;
    draftRef: { draft_id: string; revision: number; content_hash: string } | null;
  }>;
  next_cursor: string | null;
}> {
  let whereClause = undefined;
  if (opts.cursor) {
    const c = decodeExperienceCursor(opts.cursor);
    whereClause = sql`(${experiences.created_at} < ${c.created_at}::timestamptz OR (${experiences.created_at} = ${c.created_at}::timestamptz AND ${experiences.id} < ${c.id}))`;
  }

  const rows = await db
    .select({
      experience: experiences,
      draft: {
        draft_id: experienceDrafts.draft_id,
        revision: experienceDrafts.revision,
        content_hash: experienceDrafts.content_hash,
      },
      cursor_at: cursorTimestamp(experiences.created_at),
    })
    .from(experiences)
    .leftJoin(experienceDrafts, eq(experiences.id, experienceDrafts.experience_id))
    .where(whereClause)
    .orderBy(desc(experiences.created_at), desc(experiences.id))
    .limit(opts.limit + 1);

  let nextCursor: string | null = null;
  if (rows.length > opts.limit) {
    rows.pop();
    const last = rows[rows.length - 1];
    if (last) {
      nextCursor = encodeExperienceCursor({ created_at: last.cursor_at, id: last.experience.id });
    }
  }

  const items = rows.map((r) => ({
    experience: r.experience,
    draftRef: r.draft?.draft_id ? r.draft : null,
  }));

  return { items, next_cursor: nextCursor };
}

export async function insertExperienceWithDraft(
  db: ProductExecutor,
  input: {
    id: string;
    name: string;
    description?: string;
    activity_type?: string;
    updated_by?: string;
    initialDraftContent?: Record<string, unknown>;
  },
): Promise<{ experience: ExperienceRow; draft: ExperienceDraftRow }> {
  return db.transaction(async (tx) => {
    const [exp] = await tx
      .insert(experiences)
      .values({
        id: input.id,
        name: input.name,
        description: input.description ?? '',
        activity_type: input.activity_type ?? 'personality_assessment',
        revision: 0,
      })
      .returning();

    if (!exp) throw new Error('insert experience returned no row');

    const draftContent = input.initialDraftContent ?? {};
    const draftHash = computeContentHash(draftContent);
    const draftId = `draft_${input.id}`;

    const [draft] = await tx
      .insert(experienceDrafts)
      .values({
        draft_id: draftId,
        experience_id: input.id,
        revision: 0,
        content_hash: draftHash,
        content: draftContent,
        updated_by: input.updated_by ?? 'admin',
      })
      .returning();

    if (!draft) throw new Error('insert draft returned no row');

    return { experience: exp, draft };
  });
}

export type PatchExperienceResult =
  | {
      status: 'ok';
      experience: ExperienceRow;
      draftRef: { draft_id: string; revision: number; content_hash: string } | null;
    }
  | { status: 'not_found' }
  | { status: 'conflict'; current: ExperienceRow };

export async function patchExperienceMetadata(
  db: ProductExecutor,
  id: string,
  expectedRevision: number,
  patch: { name?: string; description?: string },
): Promise<PatchExperienceResult> {
  const values: Record<string, unknown> = {
    revision: sql`${experiences.revision} + CASE WHEN ${experiences.name} IS DISTINCT FROM COALESCE(${patch.name ?? null}, ${experiences.name}) OR ${experiences.description} IS DISTINCT FROM COALESCE(${patch.description ?? null}, ${experiences.description}) THEN 1 ELSE 0 END`,
    updated_at: sql`CASE WHEN ${experiences.name} IS DISTINCT FROM COALESCE(${patch.name ?? null}, ${experiences.name}) OR ${experiences.description} IS DISTINCT FROM COALESCE(${patch.description ?? null}, ${experiences.description}) THEN now() ELSE ${experiences.updated_at} END`,
  };
  if (patch.name !== undefined) values.name = patch.name;
  if (patch.description !== undefined) values.description = patch.description;

  const [updated] = await db
    .update(experiences)
    .set(values)
    .where(and(eq(experiences.id, id), eq(experiences.revision, expectedRevision)))
    .returning();

  if (updated) {
    const [draft] = await db
      .select({
        draft_id: experienceDrafts.draft_id,
        revision: experienceDrafts.revision,
        content_hash: experienceDrafts.content_hash,
      })
      .from(experienceDrafts)
      .where(eq(experienceDrafts.experience_id, id))
      .limit(1);

    return {
      status: 'ok',
      experience: updated,
      draftRef: draft ?? null,
    };
  }

  const existing = await findExperienceById(db, id);
  if (!existing) {
    return { status: 'not_found' };
  }
  return { status: 'conflict', current: existing };
}

export async function findDraftByExperienceId(
  db: ProductExecutor,
  experienceId: string,
): Promise<ExperienceDraftRow | undefined> {
  const [row] = await db
    .select()
    .from(experienceDrafts)
    .where(eq(experienceDrafts.experience_id, experienceId))
    .limit(1);
  return row;
}

export type UpdateDraftResult =
  | { status: 'ok'; draft: ExperienceDraftRow }
  | { status: 'not_found' }
  | { status: 'conflict'; current: ExperienceDraftRow };

export async function updateDraftContent(
  db: ProductExecutor,
  experienceId: string,
  expectedRevision: number,
  newContent: Record<string, unknown>,
  newHash: string,
  updatedBy: string,
): Promise<UpdateDraftResult> {
  const [updated] = await db
    .update(experienceDrafts)
    .set({
      revision: sql`${experienceDrafts.revision} + CASE WHEN ${experienceDrafts.content_hash} IS DISTINCT FROM ${newHash} THEN 1 ELSE 0 END`,
      content: newContent,
      content_hash: newHash,
      updated_by: sql`CASE WHEN ${experienceDrafts.content_hash} IS DISTINCT FROM ${newHash} THEN ${updatedBy} ELSE ${experienceDrafts.updated_by} END`,
      updated_at: sql`CASE WHEN ${experienceDrafts.content_hash} IS DISTINCT FROM ${newHash} THEN now() ELSE ${experienceDrafts.updated_at} END`,
    })
    .where(
      and(
        eq(experienceDrafts.experience_id, experienceId),
        eq(experienceDrafts.revision, expectedRevision),
      ),
    )
    .returning();

  if (updated) {
    return { status: 'ok', draft: updated };
  }

  const existing = await findDraftByExperienceId(db, experienceId);
  if (!existing) {
    return { status: 'not_found' };
  }
  return { status: 'conflict', current: existing };
}

export type InsertReleaseResult =
  | { status: 'ok'; release: ExperienceReleaseRow }
  | { status: 'duplicate_version' };

const RELEASE_VERSION_UNIQUE = 'experience_releases_exp_id_def_ver_unique';

/** Drizzle wraps the pg error in `cause`; only the definition-version constraint means a duplicate release. */
function isDuplicateVersionViolation(error: unknown): boolean {
  let e: unknown = error;
  for (let depth = 0; depth < 5 && e && typeof e === 'object'; depth += 1) {
    const { code, constraint } = e as { code?: unknown; constraint?: unknown };
    if (code === '23505') return constraint === RELEASE_VERSION_UNIQUE;
    e = (e as { cause?: unknown }).cause;
  }
  return false;
}

export async function insertExperienceRelease(
  db: ProductExecutor,
  input: {
    id: string;
    experience_id: string;
    definition_version: string;
    definition_hash: string;
    definition_schema_version: string;
    engine_version: string;
    is_demo: boolean;
    approval_refs: string[];
    validation_id: string;
    evaluation_id: string;
    content: Record<string, unknown>;
    published_by: string;
  },
): Promise<InsertReleaseResult> {
  try {
    const [row] = await db.insert(experienceReleases).values(input).returning();
    if (!row) throw new Error('insert release returned no row');
    return { status: 'ok', release: row };
  } catch (err: unknown) {
    if (isDuplicateVersionViolation(err)) {
      return { status: 'duplicate_version' };
    }
    throw err;
  }
}

export async function findReleaseById(
  db: ProductExecutor,
  releaseId: string,
): Promise<ExperienceReleaseRow | undefined> {
  const [row] = await db
    .select()
    .from(experienceReleases)
    .where(eq(experienceReleases.id, releaseId))
    .limit(1);
  return row;
}

export async function findReleaseByVersion(
  db: ProductExecutor,
  experienceId: string,
  definitionVersion: string,
): Promise<ExperienceReleaseRow | undefined> {
  const [row] = await db
    .select()
    .from(experienceReleases)
    .where(and(eq(experienceReleases.experience_id, experienceId), eq(experienceReleases.definition_version, definitionVersion)))
    .limit(1);
  return row;
}

export async function listExperienceReleases(
  db: ProductExecutor,
  experienceId: string,
  opts: { limit: number; cursor?: string },
): Promise<{ items: ExperienceReleaseRow[]; next_cursor: string | null }> {
  let whereClause = eq(experienceReleases.experience_id, experienceId);
  if (opts.cursor) {
    const c = decodeReleaseCursor(opts.cursor, experienceId);
    whereClause = and(
      eq(experienceReleases.experience_id, experienceId),
      sql`(${experienceReleases.published_at} < ${c.published_at}::timestamptz OR (${experienceReleases.published_at} = ${c.published_at}::timestamptz AND ${experienceReleases.id} < ${c.id}))`,
    )!;
  }

  const rows = await db
    .select({ release: experienceReleases, cursor_at: cursorTimestamp(experienceReleases.published_at) })
    .from(experienceReleases)
    .where(whereClause)
    .orderBy(desc(experienceReleases.published_at), desc(experienceReleases.id))
    .limit(opts.limit + 1);

  let nextCursor: string | null = null;
  if (rows.length > opts.limit) {
    rows.pop();
    const last = rows[rows.length - 1];
    if (last) {
      nextCursor = encodeReleaseCursor({ published_at: last.cursor_at, id: last.release.id }, experienceId);
    }
  }

  return { items: rows.map((row) => row.release), next_cursor: nextCursor };
}

export async function insertExperienceReport(
  db: ProductExecutor,
  report: typeof experienceReports.$inferInsert,
): Promise<ExperienceReportRow> {
  const [row] = await db.insert(experienceReports).values(report).returning();
  if (!row) throw new Error('insert experience report returned no row');
  return row;
}

export async function findReportById(
  db: ProductExecutor,
  id: string,
): Promise<ExperienceReportRow | undefined> {
  const [row] = await db
    .select()
    .from(experienceReports)
    .where(eq(experienceReports.id, id))
    .limit(1);
  return row;
}

export async function findLatestReport(
  db: ProductExecutor,
  experienceId: string,
  contentHash: string,
  kind: 'validation' | 'evaluation',
): Promise<ExperienceReportRow | undefined> {
  const [row] = await db
    .select()
    .from(experienceReports)
    .where(
      and(
        eq(experienceReports.experience_id, experienceId),
        eq(experienceReports.content_hash, contentHash),
        eq(experienceReports.kind, kind),
      ),
    )
    .orderBy(desc(experienceReports.created_at))
    .limit(1);
  return row;
}

