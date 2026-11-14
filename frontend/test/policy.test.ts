import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { parseBlocks } from '../lib/mini-md.ts';

const policy = readFileSync(new URL('../../docs/privacidad/politica-de-privacidad.md', import.meta.url), 'utf8');

test('la política cita la Ley 29733 y explica los principios', () => {
  assert.match(policy, /Ley N\.° 29733/);
  for (const p of ['Legalidad', 'Consentimiento', 'Finalidad', 'Proporcionalidad', 'Calidad', 'Seguridad',
    'Disposición de recurso', 'Nivel de protección adecuado']) {
    assert.ok(policy.includes(`**${p}:**`), `falta el principio de ${p}`);
  }
});

test('la política explica cada derecho ARCO con un ejemplo, cómo pedirlo y los plazos', () => {
  for (const right of ['Acceso', 'Rectificación', 'Cancelación', 'Oposición']) {
    assert.ok(policy.includes(`### ${right}:`), `falta el derecho de ${right}`);
  }
  assert.equal(policy.match(/\*\*Ejemplo:\*\*/g)?.length, 4);
  for (const heading of ['Cómo pedir tus derechos', 'Cuánto tardamos en responder', 'Si no estás de acuerdo']) {
    assert.ok(policy.includes(`## ${heading}`), `falta la sección "${heading}"`);
  }
  assert.match(policy, /ANPD/);
  assert.match(policy, /gratis/i);
});

test('el lector de Markdown entiende la política sin perder títulos', () => {
  const blocks = parseBlocks(policy);
  assert.equal(blocks.filter((b) => b.type === 'h1').length, 1);
  assert.equal(blocks.filter((b) => b.type === 'h3').length, 4);
});
