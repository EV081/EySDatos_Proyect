import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { Metadata } from 'next';
import { parseBlocks, type Inline } from '@/lib/mini-md';

export const metadata: Metadata = { title: 'Aviso de privacidad' };

// La fuente única es docs/privacidad/aviso-de-privacidad.md: el informe y esta página muestran el mismo texto.
const SOURCE = join(process.cwd(), '..', 'docs', 'privacidad', 'aviso-de-privacidad.md');

function Inlines({ items }: { items: Inline[] }) {
  return (
    <>
      {items.map((s, i) => (s.bold ? <strong key={i}>{s.text}</strong> : <span key={i}>{s.text}</span>))}
    </>
  );
}

export default function Page() {
  const blocks = parseBlocks(readFileSync(SOURCE, 'utf8'));
  return (
    <article className="legal">
      {blocks.map((b, i) => {
        switch (b.type) {
          case 'h1':
            return <h1 key={i}><Inlines items={b.inlines} /></h1>;
          case 'h2':
            return <h2 key={i}><Inlines items={b.inlines} /></h2>;
          case 'h3':
            return <h3 key={i}><Inlines items={b.inlines} /></h3>;
          case 'p':
            return <p key={i}><Inlines items={b.inlines} /></p>;
          case 'ul':
            return <ul key={i}>{b.items.map((it, j) => <li key={j}><Inlines items={it} /></li>)}</ul>;
          case 'ol':
            return <ol key={i}>{b.items.map((it, j) => <li key={j}><Inlines items={it} /></li>)}</ol>;
        }
      })}
    </article>
  );
}
