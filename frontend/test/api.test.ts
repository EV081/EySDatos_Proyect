import assert from 'node:assert/strict';
import { test } from 'node:test';
import { Api, ApiError } from '../lib/api.ts';

function fakeFetch(status: number, body: unknown, calls: { url: string; init?: RequestInit }[] = []) {
  return async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    return new Response(status === 204 ? null : JSON.stringify(body), { status });
  };
}

test('cada petición lleva el token y no se cachea', async () => {
  const calls: { url: string; init?: RequestInit }[] = [];
  const api = new Api('http://127.0.0.1:8001/', 'tok', fakeFetch(200, { unlocked: true }, calls));
  await api.status();
  assert.equal(calls[0].url, 'http://127.0.0.1:8001/status');
  assert.equal((calls[0].init!.headers as Record<string, string>).Authorization, 'Bearer tok');
  assert.equal(calls[0].init!.cache, 'no-store');
});

test('el cuerpo se manda como JSON y los ids se escapan en la ruta', async () => {
  const calls: { url: string; init?: RequestInit }[] = [];
  const api = new Api('http://127.0.0.1:8001', 'tok', fakeFetch(202, {}, calls));
  await api.send('12/../3', 'hola');
  assert.equal(calls[0].url, 'http://127.0.0.1:8001/conversations/12%2F..%2F3/messages');
  assert.deepEqual(JSON.parse(calls[0].init!.body as string), { text: 'hola' });
  assert.equal((calls[0].init!.headers as Record<string, string>)['Content-Type'], 'application/json');
});

test('los errores del cliente local llegan como ApiError con su código', async () => {
  const api = new Api('http://127.0.0.1:8001', 'tok', fakeFetch(409, { error: 'conflict', detail: 'la huella no coincide' }));
  await assert.rejects(() => api.verify('1', '00000'), (e: ApiError) => e instanceof ApiError && e.status === 409 && e.code === 'conflict' && e.message === 'la huella no coincide');
});

test('423 bloqueado y 401 sin token', async () => {
  await assert.rejects(() => new Api('http://x', 't', fakeFetch(423, { error: 'locked', detail: '' })).conversations(), { code: 'locked' });
  await assert.rejects(() => new Api('http://x', 't', fakeFetch(401, { detail: 'token inválido' })).status(), { code: 'unauthorized' });
  await assert.rejects(() => new Api('http://x', 't', fakeFetch(422, { detail: [{ msg: 'x' }] })).status(), { code: 'invalid' });
});

test('204 no tiene cuerpo', async () => {
  assert.equal(await new Api('http://x', 't', fakeFetch(204, null)).lock(), null);
});

test('sin red se informa como network, sin filtrar el error original', async () => {
  const api = new Api('http://x', 't', async () => { throw new TypeError('fetch failed: ECONNREFUSED 127.0.0.1'); });
  await assert.rejects(() => api.status(), (e: ApiError) => e.code === 'network' && !/ECONNREFUSED/.test(e.message));
});
