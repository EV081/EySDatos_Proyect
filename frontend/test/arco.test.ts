import assert from 'node:assert/strict';
import { test } from 'node:test';
import { Api } from '../lib/api.ts';
import { directoryErrorText, errorMessage, formatDate } from '../lib/format.ts';

function recorder() {
  const calls: { url: string; method?: string; body?: unknown }[] = [];
  const fetchImpl = async (url: string, init?: RequestInit) => {
    calls.push({ url, method: init?.method, body: init?.body ? JSON.parse(init.body as string) : undefined });
    return new Response(JSON.stringify({}), { status: 200 });
  };
  return { calls, api: new Api('http://127.0.0.1:8001', 'tok', fetchImpl) };
}

test('ARCO: cada derecho llama a su ruta del cliente local', async () => {
  const { calls, api } = recorder();
  await api.myData();
  await api.rotateKey('Clave-123456');
  await api.cancelRegistration('Clave-123456', false);
  await api.deleteLocalData('Clave-123456');
  assert.deepEqual(calls.map((c) => `${c.method} ${c.url.replace('http://127.0.0.1:8001', '')}`), [
    'GET /privacy/my-data', 'POST /identity/rotate', 'POST /identity/cancel', 'POST /identity/delete-local',
  ]);
  assert.deepEqual(calls[2].body, { password: 'Clave-123456', delete_local: false });
});

test('ARCO: los errores del directorio se explican sin tecnicismos', () => {
  assert.match(errorMessage({ code: 'login_required' }), /inicia sesión con Discord/);
  assert.match(errorMessage({ code: 'directory_error' }), /No se cambió nada/);
  assert.equal(directoryErrorText(null), null);
  assert.match(directoryErrorText('not_registered')!, /ningún registro/);
  assert.match(directoryErrorText('algo-raro')!, /no respondió/);
});

test('las fechas aceptan segundos Unix y texto ISO, y lo vacío se muestra como guion', () => {
  const unix = formatDate(1_800_000_000);
  const iso = formatDate(new Date(1_800_000_000 * 1000).toISOString());
  assert.match(unix, /^\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}$/);
  assert.equal(unix, iso);
  for (const empty of [null, undefined, '', 'no-es-fecha']) assert.equal(formatDate(empty), '—');
});

test('cambiar contraseña maestra: envía la actual y la nueva', async () => {
  const { calls, api } = recorder();
  const [actual, nueva] = ['a'.repeat(12), 'b'.repeat(12)]; // valores de prueba, no credenciales
  await api.changePassword(actual, nueva);
  assert.deepEqual(calls, [{ url: 'http://127.0.0.1:8001/identity/password', method: 'POST', body: { password: actual, new_password: nueva } }]);
});

test('quitar contacto: DELETE a la ruta del contacto, sin cuerpo', async () => {
  const { calls, api } = recorder();
  await api.removeContact('222222222222222222');
  assert.deepEqual(calls, [{ url: 'http://127.0.0.1:8001/contacts/222222222222222222', method: 'DELETE', body: undefined }]);
});
