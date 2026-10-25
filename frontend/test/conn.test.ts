import assert from 'node:assert/strict';
import { test } from 'node:test';
import { isLocal } from '../lib/conn.ts';

test('C-13: el token solo se envía a la máquina local', () => {
  assert.equal(isLocal('http://127.0.0.1:8001'), true);
  assert.equal(isLocal('http://localhost:8002/'), true);
});

test('C-13: cualquier otro destino se rechaza', () => {
  for (const bad of [
    'http://evil.example', 'http://127.0.0.1.evil.example', 'http://localhost.evil.example:80',
    'https://127.0.0.1:8001', 'http://192.168.1.10:8001', 'http://[::1]:8001', 'ftp://127.0.0.1',
    'javascript:alert(1)', '127.0.0.1:8001', '', 'http://user@evil.example@127.0.0.1', 'http://user:pw@127.0.0.1:8001',
  ]) {
    assert.equal(isLocal(bad), false, bad);
  }
});
