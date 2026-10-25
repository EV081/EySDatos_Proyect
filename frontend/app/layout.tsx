import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import './globals.css';

export const metadata: Metadata = {
  title: 'Mensajería cifrada E2EE',
  description: 'Cliente de mensajería cifrada de extremo a extremo sobre Discord',
  referrer: 'no-referrer',
};

// En producción el navegador solo puede hablar con el cliente local (127.0.0.1) y con este mismo origen.
// Next inserta scripts de arranque en línea, por eso 'unsafe-inline' en scripts; la defensa contra XSS es que
// nada de lo que llega de Discord se interpreta como HTML (todo se renderiza como texto).
const CSP = [
  "default-src 'none'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "connect-src http://127.0.0.1:* http://localhost:*",
  "img-src 'self' data:",
  "font-src 'self'",
  "base-uri 'none'",
  "form-action 'none'",
].join('; ');

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      <head>
        {process.env.NODE_ENV === 'production' && <meta httpEquiv="Content-Security-Policy" content={CSP} />}
      </head>
      <body>{children}</body>
    </html>
  );
}
