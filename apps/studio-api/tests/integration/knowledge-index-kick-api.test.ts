import { createServer, type IncomingMessage, type Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { jwtVerify } from 'jose';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { closeKnowledgePool } from '@/infrastructure/db/knowledge-client';
import { issueAccessToken } from '@/modules/auth/tokens';
import { setIndexKicker } from '@/modules/knowledge/index-kick';
import { adminSql, startKnowledgePostgres, stubKnowledgeEnv, type KnowledgeDbHandle } from '../helpers/knowledge-db';
import { api, createKb, expectDeclared } from '../helpers/knowledge-api';

const KEY = Buffer.from('studio-test-key-at-least-32-bytes!!');
let db: KnowledgeDbHandle;
let admin: string;
let runtime: Server;
let runtimeUrl: string;
let reply: { status: number; body: unknown };
const seen: Array<{ url: string; headers: IncomingMessage['headers']; body: string }> = [];
const kicks: string[] = [];

beforeAll(async () => {
  db = await startKnowledgePostgres();
  runtime = createServer((req, res) => {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      seen.push({ url: req.url ?? '', headers: req.headers, body });
      res.writeHead(reply.status, { 'content-type': 'application/json' }).end(JSON.stringify(reply.body));
    });
  });
  await new Promise<void>(resolve => runtime.listen(0, '127.0.0.1', resolve));
  runtimeUrl = `http://127.0.0.1:${(runtime.address() as AddressInfo).port}`;
});
afterAll(async () => {
  await new Promise(resolve => runtime?.close(resolve));
  try { await closeKnowledgePool(); } finally { await db?.stop(); }
});
beforeEach(async () => {
  vi.unstubAllEnvs();
  stubKnowledgeEnv(db, {
    RUNTIME_INTERNAL_URL: runtimeUrl, STUDIO_RUNTIME_SIGNING_KEY: KEY.toString('base64'), STUDIO_RUNTIME_SIGNING_KID: 'studio',
  });
  admin = await issueAccessToken('admin', true);
  seen.length = 0;
  kicks.length = 0;
  reply = { status: 202, body: { success: true, data: { status: 'started' } } };
  setIndexKicker(ctx => { kicks.push(ctx.requestId); });
});
afterEach(() => setIndexKicker(null));

const content = { title: 'PTIT', body: 'nội dung', source_url: null, metadata: {} };
const doc = (kb: string, id: string) => `/admin/knowledge-bases/${kb}/documents/${id}`;

describe('index kick after writes', () => {
  it('kicks once per effective document save, not for unchanged or failed saves', async () => {
    const kb = await createKb(admin);
    expect((await api('PUT', doc(kb, 'ptit'), admin, { ...content, expected_revision: 0 })).status).toBe(201);
    expect(kicks).toHaveLength(1);
    expect((await api('PUT', doc(kb, 'ptit'), admin, { ...content, expected_revision: 1 })).body.data.outcome).toBe('unchanged');
    expect((await api('PUT', doc(kb, 'ptit'), admin, { ...content, body: 'khác', expected_revision: 9 })).status).toBe(409);
    expect(kicks).toHaveLength(1);
    expect((await api('PUT', doc(kb, 'ptit'), admin, { ...content, body: 'mới', expected_revision: 1 })).status).toBe(200);
    expect(kicks).toHaveLength(2);
  });

  it('kicks once per import commit that wrote rows, and not on idempotent replay', async () => {
    const kb = await createKb(admin);
    const body = { idempotency_key: 'k1', rows: [
      { row: 1, document_id: 'a', expected_revision: 0, payload: content },
      { row: 2, document_id: 'b', expected_revision: 0, payload: content },
    ] };
    expect((await api('POST', `/admin/knowledge-bases/${kb}/imports`, admin, body)).status).toBe(200);
    expect(kicks).toHaveLength(1);
    expect((await api('POST', `/admin/knowledge-bases/${kb}/imports`, admin, body)).status).toBe(200);
    expect(kicks).toHaveLength(1);
  });

  it('kicks after a successful revision retry only', async () => {
    const kb = await createKb(admin);
    await api('PUT', doc(kb, 'mtu'), admin, { ...content, expected_revision: 0 });
    kicks.length = 0;
    expect((await api('POST', `${doc(kb, 'mtu')}/revisions/1/retry`, admin)).status).toBe(409);
    expect(kicks).toHaveLength(0);
    await adminSql(db, `UPDATE knowledge.document_revisions SET index_status = 'error', error = 'x' WHERE document_id = 'mtu'`);
    expect((await api('POST', `${doc(kb, 'mtu')}/revisions/1/retry`, admin)).status).toBe(200);
    expect(kicks).toHaveLength(1);
  });

  it('does not fail the write when the kick fails', async () => {
    setIndexKicker(() => Promise.reject(new Error('down')));
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const kb = await createKb(admin);
    expect((await api('PUT', doc(kb, 'ok'), admin, { ...content, expected_revision: 0 })).status).toBe(201);
  });

  it('with the real client, signs purpose knowledge.index and survives an unreachable runtime', async () => {
    setIndexKicker(null);
    const kb = await createKb(admin);
    expect((await api('PUT', doc(kb, 'real'), admin, { ...content, expected_revision: 0 })).status).toBe(201);
    await vi.waitFor(() => expect(seen).toHaveLength(1));
    expect(seen[0]!.url).toBe('/api/v1/internal/knowledge/index-runs');
    expect(seen[0]!.body).toBe('{}');
    const { payload } = await jwtVerify(String(seen[0]!.headers['x-caller-context']), new Uint8Array(KEY), {
      issuer: 'sda-studio-api', audience: 'sda-agent-runtime',
    });
    expect(payload).toMatchObject({ purpose: 'knowledge.index', request_target: '/api/v1/internal/knowledge/index-runs' });
    vi.stubEnv('RUNTIME_INTERNAL_URL', 'http://127.0.0.1:1');
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    expect((await api('PUT', doc(kb, 'real2'), admin, { ...content, expected_revision: 0 })).status).toBe(201);
  });
});

describe('POST index-runs', () => {
  const path = (kb: string) => `/admin/knowledge-bases/${kb}/index-runs`;

  it('returns 202 with the runtime status', async () => {
    setIndexKicker(null);
    const kb = await createKb(admin);
    const res = await api('POST', path(kb), admin);
    expect(res.status).toBe(202);
    expectDeclared(res.body, '/admin/knowledge-bases/{kb_id}/index-runs', 'post', 202);
    expect(res.body.data).toEqual({ status: 'started' });
    reply = { status: 202, body: { success: true, data: { status: 'already_running' } } };
    expect((await api('POST', path(kb), admin)).body.data).toEqual({ status: 'already_running' });
  });

  it('503 when the runtime is down or not configured, 404 unknown kb, 401/403 without admin', async () => {
    const kb = await createKb(admin);
    reply = { status: 503, body: { success: false } };
    const down = await api('POST', path(kb), admin);
    expect(down.status).toBe(503);
    expect(down.body.error.code).toBe('SYS_UNAVAILABLE');
    vi.stubEnv('STUDIO_RUNTIME_SIGNING_KEY', '');
    expect((await api('POST', path(kb), admin)).status).toBe(503);
    expect((await api('POST', path('missing-kb'), admin)).status).toBe(404);
    expect((await api('POST', path(kb))).status).toBe(401);
    expect((await api('POST', path(kb), await issueAccessToken('user', false))).status).toBe(403);
  });
});
