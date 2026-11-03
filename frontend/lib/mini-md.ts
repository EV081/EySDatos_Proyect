// Lector mínimo de Markdown para el aviso de privacidad: títulos, párrafos, listas y **negrita**.
// Produce datos, no HTML: la página los dibuja con React, así que nada se inserta como HTML.
export interface Inline {
  text: string;
  bold: boolean;
}

export type Block =
  | { type: 'h1' | 'h2' | 'h3'; inlines: Inline[] }
  | { type: 'p'; inlines: Inline[] }
  | { type: 'ul' | 'ol'; items: Inline[][] };

export function parseInline(text: string): Inline[] {
  const out: Inline[] = [];
  text.split(/\*\*/).forEach((part, i) => {
    if (part) out.push({ text: part, bold: i % 2 === 1 });
  });
  return out;
}

export function parseBlocks(md: string): Block[] {
  const blocks: Block[] = [];
  let para: string[] = [];
  let list: { type: 'ul' | 'ol'; items: Inline[][] } | null = null;

  const flushPara = () => {
    if (para.length) blocks.push({ type: 'p', inlines: parseInline(para.join(' ')) });
    para = [];
  };
  const flushList = () => {
    if (list) blocks.push(list);
    list = null;
  };

  for (const raw of md.split('\n')) {
    const line = raw.trimEnd();
    const heading = /^(#{1,3})\s+(.*)$/.exec(line);
    const bullet = /^-\s+(.*)$/.exec(line);
    const numbered = /^\d+\.\s+(.*)$/.exec(line);
    if (!line.trim()) {
      flushPara();
      flushList();
    } else if (heading) {
      flushPara();
      flushList();
      blocks.push({ type: `h${heading[1].length}` as 'h1' | 'h2' | 'h3', inlines: parseInline(heading[2]) });
    } else if (bullet || numbered) {
      flushPara();
      const type = bullet ? 'ul' : 'ol';
      if (list && list.type !== type) flushList();
      list = list ?? { type, items: [] };
      list.items.push(parseInline((bullet ?? numbered)![1]));
    } else {
      flushList();
      para.push(line.trim());
    }
  }
  flushPara();
  flushList();
  return blocks;
}

export function noticeVersion(md: string): string | null {
  return /\*\*Versión:\*\*\s*([0-9]+(?:\.[0-9]+)*)/.exec(md)?.[1] ?? null;
}
