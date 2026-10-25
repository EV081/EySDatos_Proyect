import assert from 'node:assert/strict';
import { test } from 'node:test';
import { noticeVersion, parseBlocks, parseInline } from '../lib/mini-md.ts';

test('negrita y texto', () => {
  assert.deepEqual(parseInline('a **b** c'), [{ text: 'a ', bold: false }, { text: 'b', bold: true }, { text: ' c', bold: false }]);
  assert.deepEqual(parseInline(''), []);
});

test('títulos, párrafos y listas', () => {
  const blocks = parseBlocks('# T\n\nuna\nlinea\n\n## S\n\n- a\n- **b**\n\n1. x\n2. y\n');
  assert.deepEqual(blocks.map((b) => b.type), ['h1', 'p', 'h2', 'ul', 'ol']);
  const p = blocks[1];
  assert.equal(p.type === 'p' && p.inlines[0].text, 'una linea');
  const ul = blocks[3];
  assert.equal(ul.type === 'ul' && ul.items.length, 2);
});

test('el HTML no se interpreta: queda como texto', () => {
  const [p] = parseBlocks('<img src=x onerror=alert(1)> **b**');
  assert.equal(p.type, 'p');
  assert.equal(p.type === 'p' && p.inlines[0].text, '<img src=x onerror=alert(1)> ');
});

test('versión del aviso', () => {
  assert.equal(noticeVersion('**Versión:** 1.0\n'), '1.0');
  assert.equal(noticeVersion('sin versión'), null);
});
