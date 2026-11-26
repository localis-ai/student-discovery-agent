import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { retrieveKnowledge, type RetrievalPayload } from '@/modules/knowledge/runtime-client';

const KEY = Buffer.from('studio-test-key-at-least-32-bytes!!');
const ctx = { requestId: 'req', traceId: 'trace' };
const payload: RetrievalPayload = { knowledge_id: 'kb_1', query: 'hello', retrieval_setting: { top_k: 3 } };

const respond = (status: number, body: unknown) =>
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(body), { status }));

describe('retrieveKnowledge', () => {
  beforeEach(() => {
    vi.stubEnv('RUNTIME_INTERNAL_URL', 'http://runtime.test');
    vi.stubEnv('STUDIO_RUNTIME_SIGNING_KEY', KEY.toString('base64'));
    vi.stubEnv('STUDIO_RUNTIME_SIGNING_KID', 'studio');
  });
  afterEach(() => { vi.unstubAllEnvs(); vi.restoreAllMocks(); });

  it('returns records and the degraded flag from a valid envelope', async () => {
    respond(200, { success: true, data: { records: [{ id: 'c1' }], degraded: true } });
    await expect(retrieveKnowledge(payload, ctx)).resolves.toEqual({ records: [{ id: 'c1' }], degraded: true });
  });

  it('treats a 200 whose data does not have the records array as unavailable', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    respond(200, { success: true, data: { records: 'nope' } });
    await expect(retrieveKnowledge(payload, ctx)).rejects.toMatchObject({ status: 503, code: 'SYS_UNAVAILABLE' });
  });

  it('passes the runtime validation issues through on a 422', async () => {
    const issues = [{ path: 'retrieval_setting.top_k', code: 'too_big', message: 'top_k too large', rule_id: null }];
    respond(422, { success: false, error: { code: 'INVALID_INPUT', message: 'bad', details: { kind: 'validation', issues } } });
    await expect(retrieveKnowledge(payload, ctx)).rejects.toMatchObject({
      status: 422,
      code: 'VAL_INVALID_INPUT',
      details: { kind: 'validation', issues },
    });
  });
});
