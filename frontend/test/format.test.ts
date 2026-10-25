import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  displayName, errorMessage, formatTime, groupDigits, messageMeta, normalizeFingerprint, preview, sessionView,
} from '../lib/format.ts';
import type { Message } from '../lib/types.ts';

const msg = (over: Partial<Message>): Message => ({ seq: 1, id: 'x', dir: 'in', text: 'hola', status: 'received', ts: 0, ...over });

test('RF9: cada estado de sesión tiene su candado y su aviso', () => {
  assert.equal(sessionView({ session: 'active' }).lock.text, '🔒 Cifrado E2EE');
  assert.equal(sessionView({ session: 'active' }).notice, null);
  assert.match(sessionView({ session: 'handshaking' }).lock.text, /Estableciendo sesión/);
  assert.equal(sessionView({ session: 'none' }).lock.tone, 'off');
  assert.equal(sessionView({ session: 'unavailable' }).notice?.kind, 'retry');
  assert.equal(sessionView({ session: 'waiting' }).notice?.kind, 'info');
});

test('RF8: un cambio de llave se muestra como alerta que pide reverificar', () => {
  const v = sessionView({ session: 'key_changed' });
  assert.equal(v.notice?.kind, 'key');
  assert.equal(v.pill?.tone, 'bad');
  assert.match(v.notice!.text, /verifiques la nueva huella/);
});

test('RF11: un mensaje no descifrable nunca muestra contenido', () => {
  assert.equal(preview(msg({ status: 'undecryptable', text: null })), 'Mensaje no descifrable');
  assert.equal(preview(msg({ dir: 'sys', status: 'key_changed', text: null })), 'Alerta de seguridad');
  assert.equal(preview(null), 'Sin mensajes');
  assert.equal(preview(msg({ text: 'hola' })), 'hola');
});

test('los mensajes salientes distinguen en cola de enviado', () => {
  assert.match(messageMeta(msg({ dir: 'out', status: 'queued' }), { verified: false }), /En cola/);
  assert.match(messageMeta(msg({ dir: 'out', status: 'sent' }), { verified: false }), /AES-256-GCM/);
  assert.match(messageMeta(msg({ status: 'received' }), { verified: true }), /Verificado/);
  assert.match(messageMeta(msg({ status: 'received' }), { verified: false }), /Sin verificar/);
  assert.match(messageMeta(msg({ status: 'undecryptable', text: null }), { verified: true }), /integridad/);
});

test('la huella se normaliza y se agrupa de a 5 dígitos', () => {
  assert.equal(normalizeFingerprint('48291 37502-68304\n75261'), '48291375026830475261');
  assert.equal(groupDigits('4829137502683047526119543847390'), '48291 37502 68304 75261 19543 84739 0');
  assert.equal(groupDigits('48291 37502'), '48291 37502');
});

test('el nombre mostrado es el alias o, si no hay, el id', () => {
  assert.equal(displayName({ alias: 'Farid', discord_id: '1' }), 'Farid');
  assert.equal(displayName({ alias: null, discord_id: '123' }), '123');
});

test('los errores se muestran en español y sin detalles internos', () => {
  assert.equal(errorMessage({ code: 'bad_password' }), 'Contraseña incorrecta.');
  assert.equal(errorMessage({ code: 'locked' }), 'Desbloquea tu identidad con tu contraseña maestra.');
  assert.equal(errorMessage({ code: 'conflict', message: 'la huella no coincide: no se verificó el contacto' }), 'la huella no coincide: no se verificó el contacto');
  assert.equal(errorMessage({ code: 'desconocido' }), 'La operación no se pudo completar.');
  assert.equal(errorMessage(new Error('boom: stack interno')), 'Ocurrió un error.');
  assert.equal(errorMessage(null), 'Ocurrió un error.');
});

test('formatTime usa dos dígitos', () => {
  assert.match(formatTime(1_800_000_000), /^\d\d:\d\d$/);
});
