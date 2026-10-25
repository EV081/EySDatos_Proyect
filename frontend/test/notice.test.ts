import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { noticeVersion } from '../lib/mini-md.ts';
import { NOTICE_VERSION } from '../lib/privacy.ts';

const read = (rel: string) => readFileSync(new URL(rel, import.meta.url), 'utf8');
const notice = read('../../docs/privacidad/aviso-de-privacidad.md');

test('C-15: la versión del aviso coincide en el documento, el frontend y el cliente local', () => {
  assert.equal(noticeVersion(notice), NOTICE_VERSION);
  assert.ok(read('../../client/privacy.py').includes(`NOTICE_VERSION = "${NOTICE_VERSION}"`));
});

test('C-15: el aviso cubre lo que la ley exige informar antes de dar los datos', () => {
  const required = [
    'Quién es el responsable',        // identidad y domicilio del titular del banco de datos
    'Qué datos tratamos',
    'Para qué usamos tus datos',      // finalidad
    'Tu consentimiento',
    'Carácter obligatorio u opcional', // y consecuencias de no darlos
    'Quién recibe tus datos',          // destinatarios
    'Transferencias internacionales',
    'Cuánto tiempo conservamos',       // plazo de conservación
    'El banco de datos',               // existencia del banco de datos
    'Tus derechos',                    // cómo ejercer ARCO
    'Cómo protegemos tus datos',
    'Cambios en este aviso',
  ];
  for (const heading of required) assert.ok(notice.includes(`## ${heading}`), `falta la sección "${heading}"`);
  for (const right of ['Acceso', 'Rectificación', 'Cancelación', 'Oposición', 'Portabilidad']) {
    assert.ok(notice.includes(`**${right}:**`), `falta el derecho de ${right}`);
  }
});

test('el aviso dice que no hay puerta trasera y avisa de los metadatos y de la contraseña', () => {
  assert.match(notice, /ninguna llave de acceso excepcional ni puerta trasera/);
  assert.match(notice, /metadatos/);
  assert.match(notice, /No hay recuperación de contraseña/);
});

test('los plazos de conservación del aviso coinciden con los de la DPIA', () => {
  const dpia = read('../../docs/dpia/DPIA.md');
  for (const plazo of ['90 días', '30 días']) {
    assert.ok(notice.includes(plazo) && dpia.includes(plazo), plazo);
  }
});
