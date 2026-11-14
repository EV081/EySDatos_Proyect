import type { Metadata } from 'next';
import { LegalDocument } from '@/components/LegalDocument';

export const metadata: Metadata = { title: 'Política de privacidad' };

// Fuente: docs/privacidad/politica-de-privacidad.md (Ley 29733 y derechos ARCO en lenguaje simple)
export default function Page() {
  return <LegalDocument file="politica-de-privacidad.md" />;
}
