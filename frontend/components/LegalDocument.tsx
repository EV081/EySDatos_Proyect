import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { parseBlocks, type Inline } from '@/lib/mini-md';

// Lee un documento de docs/privacidad/ al construir el sitio y lo dibuja con React (nada se inserta como HTML).
// La fuente única es el Markdown: el informe y la página muestran el mismo texto.
export const legalSource = (file: string) => join(process.cwd(), '..', 'docs', 'privacidad', file);

function Inlines({ items }: { items: Inline[] }) {
  return (
    <>
      {items.map((s, i) => (s.bold ? <strong key={i}>{s.text}</strong> : <span key={i}>{s.text}</span>))}
    </>
  );
}

export function LegalDocument({ file }: { file: string }) {
  const blocks = parseBlocks(readFileSync(legalSource(file), 'utf8'));
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
