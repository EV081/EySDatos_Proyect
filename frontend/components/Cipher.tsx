'use client';
import { useEffect, useState } from 'react';

// Animaciones de texto cifrado. Son solo visuales: los caracteres son aleatorios, no criptografía real.
const GLYPHS = '0123456789abcdef';
const glyph = () => GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Deja a la vista los primeros `from` caracteres y enmascara el resto (los espacios se conservan para no mover las líneas).
const mask = (chars: string[], from: number) => chars.map((c, i) => (i < from || /\s/.test(c) ? c : glyph())).join('');

// Un mensaje recién llegado se "descifra": aparece como texto cifrado y se resuelve de izquierda a derecha.
export function Decipher({ text }: { text: string }) {
  const [out, setOut] = useState<string | null>(() => (reducedMotion() ? null : mask(Array.from(text), 0)));

  useEffect(() => {
    if (reducedMotion()) return;
    const chars = Array.from(text);
    const duration = Math.min(1400, Math.max(450, 350 + chars.length * 14));
    const start = performance.now();
    let last = 0;
    let frame = requestAnimationFrame(function step(now: number) {
      const p = (now - start) / duration;
      if (p >= 1) return setOut(null);
      if (now - last > 40) {
        last = now;
        setOut(mask(chars, Math.floor(p * chars.length)));
      }
      frame = requestAnimationFrame(step);
    });
    return () => cancelAnimationFrame(frame);
  }, [text]);

  if (out === null) return <>{text}</>;
  // El lector de pantalla recibe el texto real, no el enmascarado.
  return (
    <>
      <span className="cipher" aria-hidden="true">{out}</span>
      <span className="sr-only">{text}</span>
    </>
  );
}

// Línea de texto cifrado que cambia sin parar: lo único que un tercero llega a ver.
export function CipherStream({ length = 32 }: { length?: number }) {
  const [chars, setChars] = useState<string[]>(() => Array.from({ length }, glyph));

  useEffect(() => {
    if (reducedMotion()) return;
    const timer = setInterval(() => {
      setChars((prev) => {
        const next = [...prev];
        for (let n = 0; n < 3; n++) next[Math.floor(Math.random() * next.length)] = glyph();
        return next;
      });
    }, 110);
    return () => clearInterval(timer);
  }, []);

  return <div className="cipher-stream" aria-hidden="true">{chars.join('').replace(/(.{4})(?=.)/g, '$1 ')}</div>;
}
