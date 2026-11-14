import type { Metadata } from 'next';
import { LegalDocument } from '@/components/LegalDocument';

export const metadata: Metadata = { title: 'Aviso de privacidad' };

// Fuente: docs/privacidad/aviso-de-privacidad.md
export default function Page() {
  return <LegalDocument file="aviso-de-privacidad.md" />;
}
