import assert from 'node:assert/strict';
import { test } from 'node:test';
import { isStrongPassword, passwordProblems } from '../lib/password.ts';

const ids = (p: string) => passwordProblems(p).map((r) => r.id);

test('una contraseña con longitud, mayúscula, minúscula y carácter especial es válida', () => {
  assert.equal(isStrongPassword('Contraseña-1'), true);
  assert.deepEqual(ids('Segura!2026x'), []);
});

test('cada requisito faltante se reporta', () => {
  assert.deepEqual(ids('Ab!'), ['length']);
  assert.deepEqual(ids('minusculas-solo'), ['upper']);
  assert.deepEqual(ids('MAYUSCULAS-SOLO'), ['lower']);
  assert.deepEqual(ids('SinEspeciales123'), ['special']);
  assert.deepEqual(ids(''), ['length', 'upper', 'lower', 'special']);
});

test('las letras acentuadas cuentan y el espacio no es carácter especial', () => {
  assert.deepEqual(ids('ÑANDÚ-ñandú'), []);
  assert.deepEqual(ids('Frase Larga Sin Signos'), ['special']);
});
