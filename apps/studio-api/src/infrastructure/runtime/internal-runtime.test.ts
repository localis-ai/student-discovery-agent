import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  callRuntimeAsStudio, classifyRuntimeStatus, readEnvelope, RuntimeCallError,
} from '@/infrastructure/runtime/internal-runtime';

const ctx = { requestId: 'req-1', traceId: 'trace-1' };
const request = { method: 'POST' as const, target: '/api/v1/internal/x', purpose: 'agent.validate', body: '{}', timeoutMs: 1000, ctx };

beforeEach(() => {
  vi.stubEnv('RUNTIME_INTERNAL_URL', 'http://runtime.test');
  vi.stubEnv('STUDIO_RUNTIME_SIGNING_KEY', Buffer.alloc(32, 9).toString('base64'));
  vi.stubEnv('STUDIO_RUNTIME_SIGNING_KID', 'studio');
});
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe('callRuntimeAsStudio', () => {
  it('sends a signed request with the caller and trace headers and does not follow redirects', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    await callRuntimeAsStudio({ ...request, accept: 'application/json' });
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(String(url)).toBe('http://runtime.test/api/v1/internal/x');
    expect(init).toMatchObject({ method: 'POST', body: '{}', redirect: 'error' });
    expect(init.headers).toMatchObject({
      'content-type': 'application/json', accept: 'application/json', 'x-internal-caller': 'sda-studio-api',
      'x-request-id': 'req-1', 'x-trace-id': 'trace-1',
    });
    expect(init.headers['x-caller-context']).toMatch(/^[\w-]+\.[\w-]+\.[\w-]+$/);
  });

  it('sends no body or content-type on GET', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}'));
    vi.stubGlobal('fetch', fetchMock);
    await callRuntimeAsStudio({ ...request, method: 'GET', body: '' });
    const init = fetchMock.mock.calls[0]![1];
    expect(init.body).toBeUndefined();
    expect(init.headers).not.toHaveProperty('content-type');
  });

  it('is not_configured without a valid key, and never calls out', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    vi.stubEnv('STUDIO_RUNTIME_SIGNING_KEY', 'short');
    await expect(callRuntimeAsStudio(request)).rejects.toMatchObject({ name: 'RuntimeCallError', kind: 'not_configured' });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    ['TimeoutError', new DOMException('slow', 'TimeoutError'), 'timeout'],
    ['AbortError', new DOMException('aborted', 'AbortError'), 'timeout'],
    ['a network failure', new TypeError('fetch failed'), 'dependency_down'],
  ])('classifies %s as %s', async (_label, error, kind) => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(error));
    const failure = await callRuntimeAsStudio(request).catch((e: unknown) => e);
    expect(failure).toBeInstanceOf(RuntimeCallError);
    expect(failure).toMatchObject({ kind });
  });

  it('returns any HTTP status as a response, not an error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 503 })));
    expect((await callRuntimeAsStudio(request)).status).toBe(503);
  });
});

describe('readEnvelope', () => {
  it('keeps only well-typed envelope fields and is null for non-JSON', async () => {
    expect(await readEnvelope(new Response('nope'))).toBeNull();
    expect(await readEnvelope(new Response('[1]'))).toBeNull();
    expect(await readEnvelope(new Response(JSON.stringify({ success: false, error: { code: 7, message: 'm' } }))))
      .toEqual({ success: false, data: undefined, error: { message: 'm' } });
    expect(await readEnvelope(new Response(JSON.stringify({ success: true, data: { a: 1 } }))))
      .toEqual({ success: true, data: { a: 1 } });
  });
});

describe('classifyRuntimeStatus', () => {
  it('separates a rejected key from a rejected request and an outage', () => {
    expect([401, 403, 404, 422, 429, 500, 503].map(classifyRuntimeStatus))
      .toEqual(['misconfigured', 'misconfigured', 'rejected', 'rejected', 'rejected', 'unavailable', 'unavailable']);
  });
});
